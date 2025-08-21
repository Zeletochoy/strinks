from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import NotABeerError, Shop, ShopBeer
from .parsing import keep_until_japanese, parse_milliliters, parse_price


class GoodBeerFaucets(Shop):
    short_name = "gbf"
    display_name = "Good Beer Faucets"

    async def _iter_cat_pages(self, url_template: str) -> AsyncIterator[BeautifulSoup]:
        i = 1
        while True:
            url = url_template.format(i)
            page = await fetch_text(self.session, url)
            soup = BeautifulSoup(page, "html.parser")
            yield soup
            if soup.find("a", class_="icon_next") is None:
                break
            i += 1

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        cat_page = "https://gbfbottleshoppe.com/?mode=cate&cbid=2651706&csid=0&sort=n&page={}"
        async for page in self._iter_cat_pages(cat_page):
            yield page

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[tuple[BeautifulSoup, str]]:
        items = page_soup.find_all("li", class_="prd_lst_unit")
        for item in items:
            if item.find("span", class_="prd_lst_soldout") is not None:
                continue
            link = item.find("a")
            if not link or not link.get("href"):
                continue
            url = "https://gbfbottleshoppe.com/" + link["href"]
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser"), url

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title_elem = page_soup.find("h2", class_="ttl_h2")
        if not title_elem:
            raise NotABeerError
        title = title_elem.get_text()
        raw_name = keep_until_japanese(title).strip()
        table = page_soup.find("table", class_="product_spec_table")
        if not table:
            raise NotABeerError
        price = None
        rows = table.find_all("tr")
        for row in rows:
            try:
                row_name = row.find("th").get_text().strip()
                row_value = row.find("td").get_text().strip()
            except AttributeError:
                continue
            if row_name == "販売価格":
                # Use parsing utility for price
                price = parse_price(row_value)
                if price is None:
                    raise NotABeerError
        if price is None:
            raise NotABeerError
        desc_elem = page_soup.find("div", class_="product_exp")
        if not desc_elem:
            raise NotABeerError
        desc = desc_elem.get_text().strip().split("\n", 1)[0]
        # Use parsing utility for milliliters
        ml = parse_milliliters(desc)
        if ml is None:
            raise NotABeerError
        image_elem = page_soup.find("div", class_="product_image_main")
        if not image_elem:
            raise NotABeerError
        img = image_elem.find("img")
        if not img or not img.get("src"):
            raise NotABeerError
        image_url = img["src"]
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
            async for beer_page, url in self._iter_page_beers(listing_page):
                try:
                    yield self._parse_beer_page(beer_page, url)
                except NotABeerError:
                    continue
                except Exception:
                    self.logger.exception("Error parsing page")

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://gbfbottleshoppe.com/",
            image_url="https://img21.shop-pro.jp/PA01456/392/PA01456392.jpg?cmsp_timestamp=20201016192055",
            shipping_fee=890,
        )
