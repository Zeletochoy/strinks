from typing import Optional, Set, NamedTuple

import click
from sqlalchemy.exc import IntegrityError

from strinks.api.shops import get_shop_map, Shop
from strinks.api.untappd import UntappdClient
from strinks.db import get_db, BeerDB


SHOP_MAP = get_shop_map()


class ScrapeSummary(NamedTuple):
    num_found: int
    num_untappd: int

    def __str__(self):
        return f"Scraped {self.num_found} beers, found {self.num_untappd} on untappd."


def scrape_shop(shop: Shop, db: BeerDB, untappd: UntappdClient, verbose: bool) -> ScrapeSummary:
    found_ids: Set[int] = set()
    num_found = num_untappd = 0
    with db.commit_or_rollback():
        db_shop = shop.get_db_entry(db)
    for offering in shop.iter_beers():
        num_found += 1
        res = untappd.try_find_beer(offering)
        if res is None:
            if verbose:
                print(f"{offering.raw_name}: Not found on Untappd")
            continue
        num_untappd += 1
        beer, query = res
        if verbose:
            print(
                f"[Shop] '{offering.raw_name}' -> "
                f"[Query] '{query}' -> "
                f"[Untappd] '{beer.brewery} - {beer.name}'"
            )
        try:
            with db.commit_or_rollback():
                db_beer = db.insert_beer(
                    beer_id=beer.beer_id,
                    image_url=beer.image_url,
                    name=beer.name,
                    brewery=beer.brewery,
                    style=beer.style,
                    abv=beer.abv,
                    ibu=beer.ibu,
                    rating=beer.rating,
                )
                found_ids.add(beer.beer_id)
        except IntegrityError:
            if verbose:
                print(f"Beer with ID {beer.beer_id} already in DB ({beer.brewery} - {beer.name})")
        with db.commit_or_rollback():
            db.insert_offering(
                shop=db_shop,
                beer=db_beer,
                url=offering.url,
                milliliters=offering.milliliters,
                price=offering.price,
                image_url=offering.image_url,
            )
        print(f"- {beer.brewery} - {beer.name}: {offering.price}¥ ({offering.milliliters}mL)")
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
def cli(database: Optional[click.Path], shop_name: Optional[str], verbose: bool):
    if shop_name is None:
        shops = [cls() for _, cls in SHOP_MAP.items()]
    else:
        shops = [SHOP_MAP[shop_name]()]

    untappd = UntappdClient()
    db = get_db(database)

    summary = {}

    for shop in shops:
        print(f"Scraping {shop.display_name}")
        try:
            shop_summary = scrape_shop(shop, db, untappd, verbose)
            summary[shop.display_name] = str(shop_summary)
        except Exception:
            from traceback import format_exc
            formatted = f"Error: {format_exc()}"
            summary[shop.display_name] = formatted
            print(formatted)
    print("" * 10, "Summary", "=" * 10)
    for shop_name, summary_str in summary.items():
        print(f"- {shop_name}: {summary_str}")
    print("Done.")
