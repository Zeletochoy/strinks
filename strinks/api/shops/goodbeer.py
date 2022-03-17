import re
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


class Goodbeer(Shop):
    short_name = "goodbeer"
    display_name = "Goodbeer"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        page_num = 1
        while True:
            url = f"https://goodbeer.jp/shop/shopbrand.html?search=&prize1=&page={page_num}"
            page = requests.get(url).text
            soup = BeautifulSoup(page, "html.parser")
            if soup.find("li", class_="next") is None:
                break
            yield soup
            page_num += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        has_beers = False
        for item in page_soup("dl", class_="search-item"):
            has_beers = True
            url = "https://goodbeer.jp/" + item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
        if not has_beers:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        image = page_soup.find(id="photoL").find("img")
        image_url = image["src"]
        title = image["alt"]
        detail = page_soup.find(id="product-detail")
        for link in detail("a"):
            if "shopbrand" in link.get("href"):
                jp_brewery = link.get_text().strip().split(" ", 1)[0]
                break
        else:
            raise NotABeerError
        title = re.sub(r"【[^】]*】", "", title).replace("限定醸造", "")
        name_parts = title.split(jp_brewery, 1)
        raw_name = name_parts[0] if name_parts[0] else title
        raw_name = raw_name.strip().lower()
        brewery_name, beer_name = raw_name.split(" ", 1)
        table = detail.find(id="item-table")
        for row in table("dl"):
            try:
                row_name = row.find("dt").get_text().strip()
                row_value = row.find("dd").get_text().strip()
            except AttributeError:
                continue
            if row_name == "容量":
                try:
                    ml = int(row_value.lower().replace("ml", ""))
                except ValueError:
                    raise NotABeerError
        price = int(detail.find("span", class_="price_tax_value").get_text().replace(",", ""))
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
                for beer_page, url in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_page, url)
                    except NotABeerError:
                        continue
                    except Exception as e:
                        print(f"Unexpected exception while parsing page, skipping.\n{e}")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://goodbeer.jp/",
            image_url="https://gigaplus.makeshop.jp/goodbeer/common/images/logo.jpg",
            shipping_fee=1220,
        )
