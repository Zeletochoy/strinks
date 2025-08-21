import re
from collections.abc import AsyncIterator
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_json, fetch_text
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters


def _get_json_url(beer_url: str) -> str:
    parts = list(urlparse(beer_url))
    parts[2] = parts[2] + ".oembed"  # Add .oembed to path
    return urlunparse(parts)


class Maruho(Shop):
    short_name = "maruho"
    display_name = "Maruho"

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://maruho.shop/collections/all?filter.v.availability=1&page={i}&sort_by=created-descending"
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser")
            i += 1

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[dict]:
        empty = True
        products = page_soup.find_all("div", class_="product-card")
        for product in products:
            link = product.find("a", class_="product-card-link")
            if not link or not link.get("href"):
                continue
            url = _get_json_url("https://maruho.shop/" + link["href"])
            page_json = await fetch_json(self.session, url)
            yield page_json
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_json) -> ShopBeer:
        title = page_json["title"].strip().lower()
        # Extract milliliters using parsing utility
        ml = parse_milliliters(title)
        if ml is None:
            raise NotABeerError
        # Now extract brewery and beer name with the known ml position
        title_match = re.search(r"^([^ ]+) *\d+ml */ *(.*)$", title)
        if title_match is None:
            raise NotABeerError
        beer_name = title_match.group(1)
        brewery_name = title_match.group(2)
        raw_name = f"{brewery_name} {beer_name}"
        price = int(page_json["offers"][0]["price"])
        image_url = "https:" + page_json["thumbnail_url"]
        url = page_json["url"]
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

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        async for listing_page in self._iter_pages():
            try:
                async for beer_json in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_json)
                    except NotABeerError:
                        continue
                    except Exception:
                        self.logger.exception("Error parsing page")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://maruho.shop",
            image_url="https://cdn.shopify.com/s/files/1/0357/6574/7843/files/toplogo_490x.png?v=1585044209",
            shipping_fee=1260,
        )
