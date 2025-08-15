import click
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from strinks.api.untappd import UntappdAPI
from strinks.db import BeerDB, get_db
from strinks.db.tables import Beer, Brewery


def fetch_breweries(db: BeerDB, verbose: bool) -> None:
    untappd = UntappdAPI()
    brewery_names = db.session.exec(select(Beer.brewery).distinct())
    for brewery_name in brewery_names:
        statement = select(Brewery).where(Brewery.name == brewery_name)
        existing_brewery = db.session.exec(statement).first()
        if existing_brewery is not None:
            continue
        if verbose:
            print(brewery_name)
        for brewery_result in untappd.search_breweries(brewery_name):
            try:
                with db.commit_or_rollback():
                    db_brewery = db.insert_brewery(
                        brewery_id=brewery_result.brewery_id,
                        image_url=brewery_result.image_url,
                        name=brewery_result.name,
                        country=brewery_result.country,
                    )
                if verbose:
                    print(f"  - {db_brewery}")
            except IntegrityError:
                pass  # Already exists


@click.command()
@click.option(
    "-d",
    "--database",
    type=click.Path(dir_okay=False, exists=True),
    default=None,
    help="Database path, default: <package_root>/db.sqlite",
)
@click.option("-v", "--verbose", is_flag=True, help="Display debug info")
def cli(database: click.Path | None, verbose: bool):
    db = get_db(str(database) if database is not None else None)

    fetch_breweries(db, verbose)
