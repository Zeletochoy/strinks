import re
from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters, parse_price


class IchiGoIchiAle(Shop):
    short_name = "ichigo"
    display_name = "Ichi Go Ichi Ale"

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://151l.shop/?mode=grp&gid=1978037&sort=n&page={i}"
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser")
            i += 1

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("li", class_="productlist_list"):
            if item.find("span", class_="item_soldout") is not None:
                continue
            url = "https://151l.shop/" + item.find("a")["href"]
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title_elem = page_soup.find("h2", class_="product_name")
        if not title_elem:
            raise NotABeerError
        title = title_elem.get_text().strip()
        name_match = re.search(r"[(（]([^）)]*)[）)]$", title)
        if name_match is None:
            raise NotABeerError
        raw_name = name_match.group(1).strip()

        price_elem = page_soup.find("span", class_="product_price")
        if not price_elem:
            raise NotABeerError
        price_text = price_elem.get_text().strip()
        price_match = re.search(r"税込([0-9,]+)円", price_text)
        if price_match is None:
            raise NotABeerError
        # Use parsing utility for price
        price = parse_price(price_match.group(1))
        if price is None:
            raise NotABeerError

        desc_elem = page_soup.find("div", class_="product_explain")
        if not desc_elem:
            raise NotABeerError
        desc = desc_elem.get_text()
        # Use parsing utility for milliliters
        ml = parse_milliliters(desc)
        if ml is None:
            raise NotABeerError

        img_elem = page_soup.find("img", class_="product_img_main_img")
        if not img_elem or not img_elem.get("src"):
            raise NotABeerError
        image_url = img_elem["src"]
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
            url="https://151l.shop/",
            image_url="https://img21.shop-pro.jp/PA01423/875/PA01423875.png?cmsp_timestamp=20201017123822",
            shipping_fee=950,
        )
