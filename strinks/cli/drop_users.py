from typing import Optional

import click

from strinks.db import get_db


@click.command()
@click.option(
    "-d",
    "--database",
    type=click.Path(dir_okay=False, exists=True),
    default=None,
    help="Database path, default: <package_root>/db.sqlite",
)
def cli(database: Optional[click.Path]) -> None:
    db = get_db(str(database) if database is not None else None)
    print("Dropping users table...")
    db.drop_users()
    print("Done.")
