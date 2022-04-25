from typing import Optional

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
def cli(path: Optional[click.Path]):
    """Initializes the beer database"""
    print(f"Initializing {path}...")
    print("Creating tables...")
    db = get_db(str(path) if path is not None else None, read_only=False)
    print("Inserting shops:")
    with db.commit_or_rollback():
        for shop_cls in get_shop_map().values():
            print(f"- {shop_cls.display_name}")
            shop = shop_cls()
            shop.get_db_entry(db)
    print("Done.")
