#!/usr/bin/env python3
"""
Migrate JSON cache to SQLite DeepLCache table.

This is a one-time migration script to move from the old JSON-based
cache to the new SQLite-based cache.
"""

import json
import logging
from pathlib import Path

from sqlmodel import Session, select

from ..db import get_db
from ..db.tables import DeepLCache

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).with_name("deepl_cache.json")


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

    logger.info(f"Found {len(json_cache)} entries in JSON cache")
    stats["total_entries"] = len(json_cache)

    for source_text, translated_text in json_cache.items():
        try:
            # Check if already exists
            statement = select(DeepLCache).where(DeepLCache.source_text == source_text)
            existing = session.exec(statement).first()

            if existing:
                stats["already_exists"] += 1
                logger.debug(f"Entry already exists for: {source_text[:50]}...")
                continue

            if not dry_run:
                # Create new cache entry
                cache_entry = DeepLCache(source_text=source_text, translated_text=translated_text)
                session.add(cache_entry)

            stats["migrated"] += 1

        except Exception as e:
            logger.error(f"Failed to migrate entry for '{source_text[:50]}...': {e}")
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

    # Count entries in JSON
    json_count = len(json_cache)

    # Count entries in SQLite
    from sqlalchemy import func

    sqlite_count = session.exec(select(func.count()).select_from(DeepLCache)).one()

    logger.info(f"JSON entries: {json_count}, SQLite entries: {sqlite_count}")

    return sqlite_count >= json_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate DeepL cache from JSON to SQLite")
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
