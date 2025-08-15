import re
from collections.abc import Iterator
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .utils import keep_until_japanese

session = get_retrying_session()


def _get_json_url(beer_url: str) -> str:
    parts = list(urlparse(beer_url))
    parts[2] = parts[2] + ".oembed"  # Add .oembed to path
    return urlunparse(parts)


class Beerzilla(Shop):
    short_name = "beerzilla"
    display_name = "Beerzilla"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = (
                "https://tokyo-beerzilla.myshopify.com/collections/"
                "%E3%82%AF%E3%83%A9%E3%83%95%E3%83%88%E3%83%93%E3%83%BC%E3%83%AB"
                f"?filter.v.availability=1&page={i}&sort_by=created-descending"
            )
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[dict]:
        empty = True
        for item in page_soup("div", class_="product-card"):
            url = "https://tokyo-beerzilla.myshopify.com" + item.find("a", class_="product-card-link")["href"]
            url = _get_json_url(url)
            page_json = session.get(url).json()
            yield page_json
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_json) -> ShopBeer:
        raw_name = keep_until_japanese(page_json["product_id"]).replace("-", " ").strip()
        price = int(page_json["offers"][0]["price"])
        image_url = page_json["thumbnail_url"]
        url = page_json["url"]
        desc = page_json["description"]
        match = re.search(r"([0-9０-９]+)(ml|ｍｌ)", desc.lower())
        if match is not None:
            ml = int(match.group(1))
        try:
            return ShopBeer(
                raw_name=raw_name,
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
            url="https://tokyo-beerzilla.myshopify.com",
            image_url="https://cdn.shopify.com/s/files/1/0602/0382/7424/files/logo_500x.png?v=1637972242",
            shipping_fee=1035,
        )
