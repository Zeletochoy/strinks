import re
from collections.abc import Iterator
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import normalize_numbers, parse_milliliters

session = get_retrying_session()


def _get_json_url(beer_url: str) -> str:
    parts = list(urlparse(beer_url))
    parts[2] = parts[2] + ".oembed"  # Add .oembed to path
    return urlunparse(parts)


class SlopShop(Shop):
    short_name = "slopshop"
    display_name = "Slop Shop"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://theslopshop-tokyo.myshopify.com/collections/beer2?page={i}&sort_by=created-descending"
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[dict]:
        empty = True
        for item_li in page_soup("li", class_="grid__item"):
            url = "https://theslopshop-tokyo.myshopify.com" + item_li.find("a")["href"]
            url = _get_json_url(url)
            yield session.get(url).json()
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_json: dict) -> ShopBeer:
        title = page_json["title"].lower()
        # Normalize full-width numbers before processing
        title_normalized = normalize_numbers(title)
        raw_name = re.split(r"(bottle|can)\s+[0-9]+(ml|ｍｌ)", title_normalized)[0].strip()
        price = int(page_json["offers"][0]["price"])
        image_url = "https:" + page_json["thumbnail_url"]
        url = page_json["url"]

        # Use parsing utility for milliliters
        ml = parse_milliliters(title)
        if ml is None:
            raise NotABeerError

        brewery_name = page_json["brand"].lower().strip()
        beer_name = raw_name[len(brewery_name) + 1 :]

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
            url="https://theslopshop-tokyo.myshopify.com/",
            image_url=(
                "https://theslopshop-tokyo.myshopify.com/cdn/shop/files/"
                "LOGO_yoko_Black_Base02_fe62a3fc-9ac4-4278-9e4a-d0657ff303fd_120x@2x.png?v=1642213762"
            ),
            shipping_fee=850,
        )
