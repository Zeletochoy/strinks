import logging

import click
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from strinks.api.untappd import UntappdAPI
from strinks.db import BeerDB, get_db
from strinks.db.tables import Beer, Brewery, Offering

logger = logging.getLogger(__name__)


def fetch_breweries(db: BeerDB, verbose: bool) -> None:
    """Fetch brewery information for beers in the database.

    Prioritizes breweries by number of beers with current offerings.
    """
    untappd = UntappdAPI()

    # Get breweries ordered by number of beers with current offerings
    beer_count_col = func.count(func.distinct(Beer.beer_id))
    brewery_beer_counts = db.session.exec(
        select(Beer.brewery, beer_count_col.label("beer_count"))
        .select_from(Beer)
        .join(Offering)  # Inner join ensures offering exists
        .where(col(Beer.brewery_id).is_(None))  # Only beers without brewery link
        .group_by(Beer.brewery)
        .order_by(beer_count_col.desc())
    ).all()

    if verbose:
        logger.info(f"Found {len(brewery_beer_counts)} unique breweries to fetch")

    for brewery_name, beer_count in brewery_beer_counts:
        # Check if brewery already exists
        statement = select(Brewery).where(Brewery.name == brewery_name)
        existing_brewery = db.session.exec(statement).first()
        if existing_brewery is not None:
            # Link existing brewery to beers
            with db.commit_or_rollback():
                beers_to_update = db.session.exec(
                    select(Beer).where(Beer.brewery == brewery_name, col(Beer.brewery_id).is_(None))
                ).all()
                for beer in beers_to_update:
                    beer.brewery_id = existing_brewery.brewery_id
                if verbose:
                    logger.info(f"Linked {len(beers_to_update)} beers to existing brewery: {existing_brewery}")
            continue

        if verbose:
            logger.info(f"Searching for: {brewery_name} ({beer_count} beers with offerings)")

        # Search for brewery on Untappd
        brewery_results = untappd.search_breweries(brewery_name)
        if not brewery_results:
            if verbose:
                logger.warning(f"  No results found for: {brewery_name}")
            continue

        # Use the first result (usually best match)
        brewery_result = brewery_results[0]
        try:
            with db.commit_or_rollback():
                db_brewery = db.insert_brewery(
                    brewery_id=brewery_result.brewery_id,
                    image_url=brewery_result.image_url,
                    name=brewery_result.name,
                    country=brewery_result.country,
                    # Note: search API doesn't return city/state
                )

                # Update beers with this brewery
                beers_to_update = db.session.exec(
                    select(Beer).where(Beer.brewery == brewery_name, col(Beer.brewery_id).is_(None))
                ).all()
                for beer in beers_to_update:
                    beer.brewery_id = brewery_result.brewery_id

                if verbose:
                    logger.info(f"  Created: {db_brewery}, linked {len(beers_to_update)} beers")
        except IntegrityError:
            if verbose:
                logger.warning(f"  Brewery already exists: {brewery_result.name}")


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
    # Set up logging
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(message)s",
    )

    db = get_db(str(database) if database is not None else None)
    fetch_breweries(db, verbose)
