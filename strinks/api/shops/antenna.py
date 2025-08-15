import re
from collections.abc import Iterator
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer

DIGITS = set("0123456789")

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
        raw_name = re.split(r"\([0-9０-９]+(ml|ｍｌ)\)", page_json["title"].lower())[0].strip()
        raw_name = re.sub("【[^】]*】", "", raw_name)
        if "本セット" in raw_name:
            raise NotABeerError
        price = int(page_json["offers"][0]["price"])
        image_url = "https:" + page_json["thumbnail_url"]
        url = page_json["url"]
        desc = page_json["description"]
        match = re.search(r"([0-9０-９]+)(ml|ｍｌ)", desc.lower())
        if match is not None:
            ml = int(match.group(1))
        match = re.search(r"ブリュワリー：([^<]+)<", desc.lower())
        if match is not None:
            brewery_name = match.group(1)
            beer_name = raw_name[len(brewery_name) + 1 :]
        else:
            brewery_name = beer_name = None
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
