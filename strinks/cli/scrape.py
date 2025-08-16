import logging
from typing import NamedTuple

import click
from sqlalchemy.exc import IntegrityError

from strinks.api.shops import Shop, get_shop_map
from strinks.api.untappd import UntappdClient
from strinks.db import BeerDB, get_db

SHOP_MAP = get_shop_map()
logger = logging.getLogger(__name__)


class ScrapeSummary(NamedTuple):
    num_found: int
    num_untappd: int

    def __str__(self):
        return f"Scraped {self.num_found} beers, found {self.num_untappd} on untappd."


def scrape_shop(shop: Shop, db: BeerDB, untappd: UntappdClient, verbose: bool) -> ScrapeSummary:
    found_ids: set[int] = set()
    num_found = num_untappd = 0
    with db.commit_or_rollback():
        db_shop = shop.get_db_entry(db)
    for offering in shop.iter_beers():
        num_found += 1
        res = untappd.try_find_beer(offering)
        if res is None:
            if verbose:
                logger.debug(f"{offering.raw_name}: Not found on Untappd")
            continue
        num_untappd += 1
        beer, query = res
        if verbose:
            logger.debug(
                f"[Shop] '{offering.raw_name}' -> [Query] '{query}' -> [Untappd] '{beer.brewery} - {beer.name}'"
            )
        try:
            with db.commit_or_rollback():
                db_beer = db.insert_beer(
                    beer_id=beer.beer_id,
                    image_url=beer.image_url,
                    name=beer.name,
                    brewery=beer.brewery,
                    brewery_id=beer.brewery_id,
                    brewery_country=beer.brewery_country,
                    brewery_city=beer.brewery_city,
                    brewery_state=beer.brewery_state,
                    style=beer.style,
                    abv=beer.abv,
                    ibu=beer.ibu,
                    rating=beer.rating,
                    weighted_rating=beer.weighted_rating,
                    rating_count=beer.rating_count,
                    total_user_count=beer.total_user_count,
                    description=beer.description,
                )
                found_ids.add(beer.beer_id)
        except IntegrityError:
            if verbose:
                logger.debug(f"Beer with ID {beer.beer_id} already in DB ({beer.brewery} - {beer.name})")
        with db.commit_or_rollback():
            db.insert_offering(
                shop=db_shop,
                beer=db_beer,
                url=offering.url,
                milliliters=offering.milliliters,
                price=offering.price,
                image_url=offering.image_url,
            )
        logger.info(f"  {beer.brewery} - {beer.name}: {offering.price}¥ ({offering.milliliters}mL)")
    with db.commit_or_rollback():
        db.remove_expired_offerings(db_shop, found_ids)
    return ScrapeSummary(num_found, num_untappd)


@click.command()
@click.option(
    "-d",
    "--database",
    type=click.Path(dir_okay=False, exists=True),
    default=None,
    help="Database path, default: <package_root>/db.sqlite",
)
@click.option("-s", "--shop-name", type=click.Choice(list(SHOP_MAP)), default=None, help="Shop name, default: all")
@click.option("-v", "--verbose", is_flag=True, help="Display debug info")
def cli(database: click.Path | None, shop_name: str | None, verbose: bool):
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",  # Simple format, just the message
    )

    # Silence HTTP request logs from urllib3 (used by requests)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    shops = [cls() for _, cls in SHOP_MAP.items()] if shop_name is None else [SHOP_MAP[shop_name]()]

    untappd = UntappdClient()
    db = get_db(str(database) if database is not None else None)

    summary = {}

    try:
        for shop in shops:
            logger.info(f"\n[{shop.display_name}]")
            try:
                shop_summary = scrape_shop(shop, db, untappd, verbose)
                summary[shop.display_name] = str(shop_summary)
            except Exception:
                from traceback import format_exc

                formatted = f"Error: {format_exc()}" if verbose else "Error: Failed to scrape shop"
                summary[shop.display_name] = formatted
                logger.error(formatted)
    finally:
        logger.info("\n" + "=" * 30 + " Summary " + "=" * 30)
        for shop_name, summary_str in summary.items():
            logger.info(f"{shop_name}: {summary_str}")
    logger.info("Done.")
