import re
from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters, parse_price


class Chouseiya(Shop):
    short_name = "chouseiya"
    display_name = "Chouseiya"

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://beer-chouseiya.shop/shopbrand/all_items/page{i}"
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser")
            i += 1

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[tuple[BeautifulSoup, str]]:
        empty = True
        items = page_soup.find_all("div", class_="innerBox")
        for item in items:
            link = item.find("a")
            if not link or not link.get("href"):
                continue
            url = "https://beer-chouseiya.shop" + link["href"]
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        if page_soup.find("p", class_="soldout") is not None:
            raise NotABeerError
        info = page_soup.find("div", id="itemInfo")
        if not info:
            raise NotABeerError
        title_elem = info.find("h2")
        if not title_elem:
            raise NotABeerError
        title = title_elem.get_text().strip().lower()
        title_match = re.search(r"【(.*?)(?:\([^)]+\))?/(.*?)(?:\([^)]+\))?】", title)
        if title_match is None:
            raise NotABeerError
        beer_name = title_match.group(1)
        brewery_name = title_match.group(2)
        price_elem = info.find("tr", id="M_usualValue")
        if not price_elem:
            raise NotABeerError
        price_str = price_elem.get_text().strip()
        # Use parsing utility for price
        price = parse_price(price_str)
        if price is None:
            raise NotABeerError

        desc_elem = page_soup.find("div", class_="detailTxt")
        if not desc_elem:
            raise NotABeerError
        desc = desc_elem.get_text().strip()
        # Use parsing utility for milliliters
        ml = parse_milliliters(desc)
        if ml is None:
            raise NotABeerError
        img_div = page_soup.find("div", id="itemImg")
        if not img_div:
            raise NotABeerError
        img_link = img_div.find("a")
        if not img_link or not img_link.get("href"):
            raise NotABeerError
        image_href = img_link["href"]
        image_match = re.search(r"imageview\('(.*)'\)", image_href)
        if image_match is None:
            raise NotABeerError
        image_url = "https://makeshop-multi-images.akamaized.net/chouseiya/itemimages/" + image_match.group(1)
        return ShopBeer(
            raw_name=f"{brewery_name} {beer_name}",
            url=url,
            brewery_name=brewery_name,
            beer_name=beer_name,
            milliliters=ml,
            price=price,
            quantity=1,
            image_url=image_url,
        )

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        async for listing_page in self._iter_pages():
            try:
                async for beer_page, url in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_page, url)
                    except NotABeerError:
                        continue
                    except Exception:
                        self.logger.exception("Error parsing page")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://beer-chouseiya.shop",
            image_url="https://shop20-makeshop.akamaized.net/shopimages/chouseiya/logo.png",
            shipping_fee=790,
            free_shipping_over=15000,
        )
