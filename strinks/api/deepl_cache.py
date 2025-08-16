"""SQLite-based cache for DeepL translations."""

from sqlmodel import Session, select

from ..db.models import BeerDB
from ..db.tables import DeepLCache


class DeepLSQLiteCache:
    """Simple cache for DeepL translations using SQLite."""

    def __init__(self, db: BeerDB):
        self.db = db
        self.session: Session = db.session

    def get(self, source_text: str) -> str | None:
        """Get cached translation for source text."""
        statement = select(DeepLCache).where(DeepLCache.source_text == source_text)
        cache_entry = self.session.exec(statement).first()
        return cache_entry.translated_text if cache_entry else None

    def set(self, source_text: str, translated_text: str) -> None:
        """Cache a translation."""
        # Check if entry exists
        statement = select(DeepLCache).where(DeepLCache.source_text == source_text)
        existing = self.session.exec(statement).first()

        if existing:
            # Update existing entry
            existing.translated_text = translated_text
        else:
            # Create new entry
            cache_entry = DeepLCache(source_text=source_text, translated_text=translated_text)
            self.session.add(cache_entry)

        self.session.commit()
