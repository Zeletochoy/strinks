"""SQLite-based cache for Untappd beer lookups."""

from datetime import timedelta
from enum import Enum

from sqlmodel import Session, select

from ...db.models import BeerDB
from ...db.tables import UntappdCache
from ..utils import now_jst


class CacheStatus(Enum):
    """Status of cache lookup result."""

    HIT = "hit"  # Found in cache and not expired
    MISS = "miss"  # Not in cache at all
    EXPIRED = "expired"  # In cache but expired


class UntappdSQLiteCache:
    """Cache for Untappd beer lookups using SQLite instead of JSON file."""

    def __init__(self, db: BeerDB, cache_duration: timedelta = timedelta(days=30)):
        self.db = db
        self.session: Session = db.session
        self.cache_duration = cache_duration

    def get(self, query: str) -> tuple[int | None, CacheStatus]:
        """
        Get cached beer_id for a query string.

        Returns:
            Tuple of (beer_id, status):
            - (beer_id, HIT): Found in cache and valid, beer_id can be None (not found on Untappd) or int
            - (None, MISS): Never cached this query
            - (None, EXPIRED): Was cached but expired
        """
        statement = select(UntappdCache).where(UntappdCache.query == query)
        cache_entry = self.session.exec(statement).first()

        if not cache_entry:
            return None, CacheStatus.MISS

        # Handle both naive and aware datetimes (SQLite might return naive)
        expires_at = cache_entry.expires_at
        if expires_at.tzinfo is None:
            from ..utils import JST

            expires_at = expires_at.replace(tzinfo=JST)

        if expires_at <= now_jst():
            return None, CacheStatus.EXPIRED

        return cache_entry.beer_id, CacheStatus.HIT

    def set(self, query: str, beer_id: int | None) -> None:
        """
        Cache a beer lookup result.

        Args:
            query: The search query string
            beer_id: The found beer_id (or None if not found)
        """
        now = now_jst()
        expires_at = now + self.cache_duration

        # Check if entry exists
        statement = select(UntappdCache).where(UntappdCache.query == query)
        existing = self.session.exec(statement).first()

        if existing:
            # Update existing entry
            existing.beer_id = beer_id
            existing.created_at = now
            existing.expires_at = expires_at
        else:
            # Create new entry
            cache_entry = UntappdCache(query=query, beer_id=beer_id, created_at=now, expires_at=expires_at)
            self.session.add(cache_entry)

        self.session.commit()

    def is_expired(self, query: str) -> bool:
        """Check if a cached entry is expired."""
        statement = select(UntappdCache).where(UntappdCache.query == query)
        cache_entry = self.session.exec(statement).first()

        if not cache_entry:
            return True

        return cache_entry.expires_at <= now_jst()

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        from sqlalchemy import delete
        from sqlmodel import col

        statement = delete(UntappdCache).where(col(UntappdCache.expires_at) <= now_jst())
        result = self.session.execute(statement)
        self.session.commit()

        return result.rowcount or 0  # type: ignore[attr-defined]

    def get_stats(self) -> dict:
        """Get cache statistics."""
        from sqlalchemy import func
        from sqlmodel import col

        total = self.session.exec(select(func.count()).select_from(UntappdCache)).one()
        expired = self.session.exec(
            select(func.count()).select_from(UntappdCache).where(col(UntappdCache.expires_at) <= now_jst())
        ).one()
        found = self.session.exec(
            select(func.count()).select_from(UntappdCache).where(col(UntappdCache.beer_id).isnot(None))
        ).one()

        return {
            "total_entries": total,
            "expired_entries": expired,
            "valid_entries": total - expired,
            "found_beers": found,
            "not_found": total - found,
        }
