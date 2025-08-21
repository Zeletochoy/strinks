from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import clean_beer_name, parse_milliliters, parse_price


class Goodbeer(Shop):
    short_name = "goodbeer"
    display_name = "Goodbeer"

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        page_num = 1
        while True:
            url = f"https://goodbeer.jp/shop/shopbrand.html?search=&prize1=&page={page_num}"
            page = await fetch_text(self.session, url)
            soup = BeautifulSoup(page, "html.parser")
            if soup.find("li", class_="next") is None:
                break
            yield soup
            page_num += 1

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[tuple[BeautifulSoup, str]]:
        has_beers = False
        for item in page_soup.find_all("dl", class_="search-item"):
            has_beers = True
            url = "https://goodbeer.jp/" + item.find("a")["href"]
            page = await fetch_text(self.session, url)
            yield BeautifulSoup(page, "html.parser"), url
        if not has_beers:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        photo_div = page_soup.find(id="photoL")
        if not photo_div:
            raise NotABeerError
        image = photo_div.find("img")
        if not image:
            raise NotABeerError
        image_url = image["src"]
        title = image["alt"]
        detail = page_soup.find(id="product-detail")
        if not detail:
            raise NotABeerError
        for link in detail.find_all("a"):
            if "shopbrand" in link.get("href"):
                jp_brewery = link.get_text().strip().split(" ", 1)[0]
                break
        else:
            raise NotABeerError
        # Use parsing utility for cleaning
        title = clean_beer_name(title)
        name_parts = title.split(jp_brewery, 1)
        if name_parts[0]:  # Has english name
            raw_name = name_parts[0]
            brewery_name, beer_name = raw_name.split(" ", 1)
        else:
            raw_name = title
            brewery_name, beer_name = name_parts
        raw_name = raw_name.strip().lower()
        table = detail.find(id="item-table")
        if not table:
            raise NotABeerError
        ml = None
        for row in table.find_all("dl"):
            try:
                row_name = row.find("dt").get_text().strip()
                row_value = row.find("dd").get_text().strip()
            except AttributeError:
                continue
            if row_name == "容量":
                # Use parsing utility for milliliters
                ml = parse_milliliters(row_value)
                if ml is None:
                    raise NotABeerError
        if ml is None:
            raise NotABeerError
        # Use parsing utility for price
        price_text = detail.find("span", class_="price_tax_value").get_text()
        price = parse_price(price_text)
        if price is None:
            raise NotABeerError
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
                async for beer_page, url in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_page, url)
                    except NotABeerError:
                        continue
                    except Exception:
                        self.logger.exception(f"Error parsing {url}")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://goodbeer.jp/",
            image_url="https://gigaplus.makeshop.jp/goodbeer/common/images/logo.jpg",
            shipping_fee=1220,
        )
