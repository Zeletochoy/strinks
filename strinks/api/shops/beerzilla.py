from collections.abc import AsyncIterator
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_json, fetch_text
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import keep_until_japanese, parse_milliliters


def _get_json_url(beer_url: str) -> str:
    parts = list(urlparse(beer_url))
    parts[2] = parts[2] + ".oembed"  # Add .oembed to path
    return urlunparse(parts)


class Beerzilla(Shop):
    short_name = "beerzilla"
    display_name = "Beerzilla"

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        i = 1
        while True:
            # Updated to use the new collection URL (新着商品 = new arrivals)
            url = (
                "https://tokyo-beerzilla.myshopify.com/collections/"
                "%E6%96%B0%E7%9D%80%E5%95%86%E5%93%81"
                f"?filter.v.availability=1&page={i}&sort_by=created-descending"
            )
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser")
            i += 1

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[dict]:
        empty = True
        for item in page_soup("div", class_="product-card"):
            url = "https://tokyo-beerzilla.myshopify.com" + item.find("a", class_="product-card-link")["href"]
            url = _get_json_url(url)
            page_json = await fetch_json(self.session, url)
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

        # Use parsing utility for milliliters
        ml = parse_milliliters(desc)
        if ml is None:
            raise NotABeerError

        return ShopBeer(
            raw_name=raw_name,
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
            url="https://tokyo-beerzilla.myshopify.com",
            image_url="https://cdn.shopify.com/s/files/1/0602/0382/7424/files/logo_500x.png?v=1637972242",
            shipping_fee=1035,
        )
