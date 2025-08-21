import asyncio

import aiohttp
import click

from ..api.shops import get_shop_map
from ..db import get_db


@click.command()
@click.option(
    "-p",
    "--path",
    type=click.Path(dir_okay=False),
    default=None,
    help="Database path, default: <package_root>/db.sqlite",
)
def cli(path: click.Path | None):
    """Initializes the beer database"""
    asyncio.run(_init_db(path))


async def _init_db(path: click.Path | None):
    """Async initialization of the beer database"""
    print(f"Initializing {path}...")
    print("Creating tables...")
    db = get_db(str(path) if path is not None else None, read_only=False)
    print("Inserting shops:")

    async with aiohttp.ClientSession() as session:
        shop_map = await get_shop_map(session)
        with db.commit_or_rollback():
            for shop_factory in shop_map.values():
                shop = shop_factory(session)
                print(f"- {shop.display_name}")
                shop.get_db_entry(db)
    print("Done.")
