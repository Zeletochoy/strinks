from collections.abc import Iterator
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import (
    clean_beer_name,
    extract_brewery_from_description,
    is_beer_set,
    parse_milliliters,
)

session = get_retrying_session()


def _get_json_url(beer_url: str) -> str:
    parts = list(urlparse(beer_url))
    parts[2] = parts[2] + ".oembed"  # Add .oembed to path
    return urlunparse(parts)


class AntennaAmerica(Shop):
    short_name = "antenna"
    display_name = "Antenna America"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://www.antenna-america.com/collections/beer?page={i}&sort_by=created-descending"
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[dict]:
        empty = True
        for item_li in page_soup("li", class_="grid__item"):
            url = "https://www.antenna-america.com" + item_li.find("a")["href"]
            url = _get_json_url(url)
            yield session.get(url).json()
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_json: dict) -> ShopBeer:
        # Clean the title
        raw_name = clean_beer_name(page_json["title"].lower())

        # Check if it's a beer set
        if is_beer_set(raw_name):
            raise NotABeerError

        price = int(page_json["offers"][0]["price"])
        image_url = "https:" + page_json["thumbnail_url"]
        url = page_json["url"]
        desc = page_json["description"]

        # Parse milliliters from description
        ml = parse_milliliters(desc)
        if ml is None:
            raise NotABeerError

        # Extract brewery from description
        brewery_name = extract_brewery_from_description(desc)
        if brewery_name:
            beer_name = raw_name[len(brewery_name) + 1 :] if raw_name.startswith(brewery_name) else raw_name
        else:
            brewery_name = beer_name = None

        return ShopBeer(
            raw_name=raw_name,
            brewery_name=brewery_name,
            beer_name=beer_name,
            url=url,
            milliliters=ml,
            price=price,
            quantity=1,
            image_url=image_url,
        )

    def iter_beers(self) -> Iterator[ShopBeer]:
        for listing_page in self._iter_pages():
            try:
                for beer_item in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_item)
                    except NotABeerError:
                        continue
                    except Exception as e:
                        print(f"Unexpected exception while parsing page, skipping.\n{e}")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://www.antenna-america.com/",
            image_url=(
                "https://cdn.shopify.com/s/files/1/0464/5673/3857/files/"
                "5c8b665f-0054-4741-94eb-1052c0a8b503_180x.png?v=1599641216"
            ),
            shipping_fee=990,
        )
