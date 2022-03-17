import re
from typing import Iterator
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


def _get_json_url(beer_url: str) -> str:
    parts = list(urlparse(beer_url))
    parts[2] = parts[2] + ".oembed"  # Add .oembed to path
    return urlunparse(parts)


class Maruho(Shop):
    short_name = "maruho"
    display_name = "Maruho"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://maruho.shop/collections/all?filter.v.availability=1&page={i}&sort_by=created-descending"
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[dict]:
        empty = True
        for product in page_soup("div", class_="product"):
            link = product.find("a", class_="product-link")
            url = _get_json_url("https://maruho.shop/" + link["href"])
            page_json = requests.get(url).json()
            yield page_json
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_json) -> ShopBeer:
        title = page_json["title"].strip().lower()
        title_match = re.search(r"^([^ ]+) *([0-9]{3,4})ml */ *(.*)$", title)
        if title_match is None:
            raise NotABeerError
        beer_name = title_match.group(1)
        ml = int(title_match.group(2))
        brewery_name = title_match.group(3)
        raw_name = f"{brewery_name} {beer_name}"
        price = int(page_json["offers"][0]["price"])
        image_url = "https" + page_json["thumbnail_url"]
        url = page_json["url"]
        try:
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
        except UnboundLocalError:
            raise NotABeerError

    def iter_beers(self) -> Iterator[ShopBeer]:
        for listing_page in self._iter_pages():
            try:
                for beer_json in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_json)
                    except NotABeerError:
                        continue
                    except Exception as e:
                        print(f"Unexpected exception while parsing page, skipping.\n{e}")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://maruho.shop",
            image_url="https://cdn.shopify.com/s/files/1/0357/6574/7843/files/toplogo_490x.png?v=1585044209",
            shipping_fee=1260,
        )
