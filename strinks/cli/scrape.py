import asyncio
import logging
from typing import NamedTuple

import click
from sqlalchemy.exc import IntegrityError

from strinks.api.shops import Shop, get_shop_map
from strinks.api.untappd import UntappdClient
from strinks.db import BeerDB, get_db

logger = logging.getLogger(__name__)


class ScrapeSummary(NamedTuple):
    num_found: int
    num_untappd: int

    def __str__(self):
        return f"Scraped {self.num_found} beers, found {self.num_untappd} on untappd."


async def scrape_shop(shop: Shop, db: BeerDB, untappd: UntappdClient, verbose: bool) -> ScrapeSummary:
    found_ids: set[int] = set()
    num_found = num_untappd = 0
    with db.commit_or_rollback():
        db_shop = shop.get_db_entry(db)
    async for offering in shop.iter_beers():
        num_found += 1
        res = await untappd.try_find_beer(offering)
        if res is None:
            if verbose:
                # Show the queries that were tried
                queries = list(offering.iter_untappd_queries())
                queries_str = " | ".join(f'"{q}"' for q in queries)  # Show all queries
                logger.debug(f"{offering.raw_name}: Not found on Untappd. Tried: {queries_str}")
            continue
        num_untappd += 1
        beer, query = res
        if verbose:
            logger.debug(
                f"[Shop] '{offering.raw_name}' -> [Query] '{query}' -> [Untappd] '{beer.brewery} - {beer.name}'"
            )
        try:
            with db.commit_or_rollback():
                # First ensure brewery exists
                if beer.brewery_id is not None and beer.brewery_country:
                    db.insert_brewery(
                        brewery_id=beer.brewery_id,
                        image_url="",  # We don't have brewery image from beer response
                        name=beer.brewery,
                        country=beer.brewery_country,
                        city=beer.brewery_city,
                        state=beer.brewery_state,
                        check_existence=True,
                    )

                # Then insert the beer
                db_beer = db.insert_beer(
                    beer_id=beer.beer_id,
                    image_url=beer.image_url,
                    name=beer.name,
                    brewery_id=beer.brewery_id,
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
@click.option(
    "-s",
    "--shop-name",
    multiple=True,
    help="Shop name(s), can be specified multiple times. For CBM and IBrew, use format like 'cbm-jimbocho'. Default: all",
)
@click.option("-v", "--verbose", is_flag=True, help="Display debug info")
@click.option("-p", "--parallel", type=int, default=1, help="Number of parallel workers (default: 1)")
def cli(database: click.Path | None, shop_name: tuple[str, ...], verbose: bool, parallel: int):
    """Run the async scraper."""
    asyncio.run(async_main(database, shop_name, verbose, parallel))


async def async_main(database: click.Path | None, shop_name: tuple[str, ...], verbose: bool, parallel: int):
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",  # Simple format, just the message
    )

    # Silence HTTP request logs from urllib3 (used by requests)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # Silence OpenAI/httpx debug logs
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    from strinks.api.async_utils import get_async_session

    db = get_db(str(database) if database is not None else None)

    summary: dict[str, str] = {}

    async with get_async_session() as session:
        untappd = UntappdClient(session)
        # Get the shop map with location expansion
        shop_map = await get_shop_map(session)

        # Create shop instances with session
        shops = []

        if not shop_name:
            # Get all shops - locations already expanded in shop_map
            for shop_key, shop_factory in shop_map.items():
                try:
                    shop = shop_factory(session)
                    shops.append(shop)
                except TypeError:
                    # Skip if constructor doesn't match
                    logger.warning(f"Could not instantiate {shop_key}")
                    continue
        else:
            # Specific shops requested
            for name in shop_name:
                if name in shop_map:
                    shop_factory = shop_map[name]
                    try:
                        shop = shop_factory(session)
                        shops.append(shop)
                    except TypeError as e:
                        logger.error(f"Could not instantiate {name}: {e}")
                else:
                    logger.error(f"Unknown shop: {name}")
                    continue

        if parallel > 1:
            # Parallel execution
            logger.info(f"Scraping {len(shops)} shops with {parallel} workers in parallel...")

            async def scrape_task(shop: Shop) -> tuple[str, str]:
                logger.info(f"[{shop.display_name}] Starting scrape")
                try:
                    shop_summary = await scrape_shop(shop, db, untappd, verbose)
                    result = str(shop_summary)
                    logger.info(f"[{shop.display_name}] {result}")
                    return shop.display_name, result
                except Exception as e:
                    from traceback import format_exc

                    if verbose:
                        logger.error(f"[{shop.display_name}] Error: {format_exc()}")
                    else:
                        logger.error(f"[{shop.display_name}] Error: {e}")
                    return shop.display_name, f"Error: {type(e).__name__}"

            # Run tasks with limited concurrency
            tasks = [scrape_task(shop) for shop in shops]
            results = await asyncio.gather(*tasks)

            for name, result in results:
                summary[name] = result
        else:
            # Sequential execution (original behavior)
            for shop in shops:
                logger.info(f"\n[{shop.display_name}]")
                try:
                    shop_summary = await scrape_shop(shop, db, untappd, verbose)
                    summary[shop.display_name] = str(shop_summary)
                except Exception as e:
                    from traceback import format_exc

                    if verbose:
                        logger.error(f"Error: {format_exc()}")
                    else:
                        logger.error(f"Error: {e}")
                    summary[shop.display_name] = f"Error: {type(e).__name__}"

    # Print final summary
    logger.info("\n" + "=" * 30 + " Summary " + "=" * 30)
    if not summary:
        logger.error("Summary dictionary is empty!")
    for name, summary_str in summary.items():
        logger.info(f"{name}: {summary_str}")
    logger.info("Done.")
