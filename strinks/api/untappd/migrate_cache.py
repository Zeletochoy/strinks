#!/usr/bin/env python3
"""
Migrate JSON cache to SQLite UntappdCache table.

This is a one-time migration script to move from the old JSON-based
cache to the new SQLite-based cache.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import Session, select

from ...db import get_db
from ...db.tables import UntappdCache
from ..utils import JST, now_jst

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).with_name("untappd_cache.json")
CACHE_DURATION = timedelta(days=30)


def migrate_json_to_sqlite(dry_run: bool = False) -> dict:
    """
    Migrate the JSON cache file to SQLite.

    Args:
        dry_run: If True, don't actually write to database

    Returns:
        Statistics about the migration
    """
    stats = {
        "total_entries": 0,
        "migrated": 0,
        "already_exists": 0,
        "expired_skipped": 0,
        "errors": 0,
    }

    if not CACHE_PATH.exists():
        logger.info(f"No cache file found at {CACHE_PATH}")
        return stats

    try:
        with open(CACHE_PATH) as f:
            json_cache = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load cache file: {e}")
        return stats

    db = get_db()
    session: Session = db.session
    now = now_jst()

    logger.info(f"Found {len(json_cache)} entries in JSON cache")
    stats["total_entries"] = len(json_cache)

    for query, (beer_id, timestamp) in json_cache.items():
        try:
            # Convert timestamp to datetime
            created_at = datetime.fromtimestamp(timestamp, tz=JST)
            expires_at = created_at + CACHE_DURATION

            # Skip if expired
            if expires_at <= now:
                stats["expired_skipped"] += 1
                continue

            # Check if already exists
            statement = select(UntappdCache).where(UntappdCache.query == query)
            existing = session.exec(statement).first()

            if existing:
                stats["already_exists"] += 1
                logger.debug(f"Entry already exists for query: {query}")
                continue

            if not dry_run:
                # Create new cache entry
                cache_entry = UntappdCache(query=query, beer_id=beer_id, created_at=created_at, expires_at=expires_at)
                session.add(cache_entry)

            stats["migrated"] += 1

        except Exception as e:
            logger.error(f"Failed to migrate entry for query '{query}': {e}")
            stats["errors"] += 1

    if not dry_run:
        session.commit()
        logger.info(f"Migration complete: {stats}")
    else:
        logger.info(f"Dry run complete (no changes made): {stats}")

    return stats


def verify_migration() -> bool:
    """Verify that migration was successful by comparing counts."""
    if not CACHE_PATH.exists():
        logger.warning("No JSON cache file to verify against")
        return True

    try:
        with open(CACHE_PATH) as f:
            json_cache = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load cache file for verification: {e}")
        return False

    db = get_db()
    session: Session = db.session

    # Count non-expired entries in JSON
    now = now_jst()
    json_valid = sum(
        1
        for _, (_, timestamp) in json_cache.items()
        if datetime.fromtimestamp(timestamp, tz=JST) + CACHE_DURATION > now
    )

    # Count entries in SQLite
    from sqlalchemy import func

    sqlite_count = session.exec(
        select(func.count()).select_from(UntappdCache).where(UntappdCache.expires_at > now)
    ).one()

    logger.info(f"JSON valid entries: {json_valid}, SQLite entries: {sqlite_count}")

    return sqlite_count >= json_valid


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate Untappd cache from JSON to SQLite")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually write to database")
    parser.add_argument("--verify", action="store_true", help="Verify migration after completion")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    stats = migrate_json_to_sqlite(dry_run=args.dry_run)

    if args.verify and not args.dry_run:
        if verify_migration():
            logger.info("Migration verified successfully")
        else:
            logger.error("Migration verification failed")
            exit(1)
