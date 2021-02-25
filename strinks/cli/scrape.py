from typing import Optional, Set

import click
from sqlalchemy.exc import IntegrityError

from strinks.api.shops import get_shop_map, Shop
from strinks.api.untappd import UntappdAPI
from strinks.db import get_db, BeerDB


SHOP_MAP = get_shop_map()


def scrape_shop(shop: Shop, db: BeerDB, untappd: UntappdAPI, verbose: bool) -> None:
    found_ids: Set[int] = set()
    with db.commit_or_rollback():
        db_shop = shop.get_db_entry(db)
    for offering in shop.iter_beers():
        res = untappd.try_find_beer(offering)
        if res is None:
            if verbose:
                print(f"{offering.raw_name}: Not found on Untappd")
        else:
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

    untappd = UntappdAPI()
    db = get_db(database)

    for shop in shops:
        print(f"Scraping {shop.display_name}")
        try:
            scrape_shop(shop, db, untappd, verbose)
        except Exception as e:
            print(f"Error: {e}")
    print("Done.")
