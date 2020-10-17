import re
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


DIGITS = set("0123456789")


class AntennaAmerica(Shop):
    short_name = "antenna"
    display_name = "Antenna America"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://www.antenna-america.com/search/is_stock:1/page:{i}"
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("div", class_="item-info"):
            url = "https://www.antenna-america.com" + item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find(id="PartsItemTitle").get_text().split(" / ", 1)[0].strip()
        if "Pack】" in title:
            raise NotABeerError
        raw_name = re.sub(" *([【].*[】]|[(].*[)]) *", "", title)
        price = int("".join(c for c in page_soup.find("h3", class_="item-price")("span")[-1].get_text() if c in DIGITS))
        table = page_soup.find(id="PartsItemAttribute")
        for row in table("tr"):
            try:
                row_name = row.find("th").get_text().strip()
                row_value = row.find("td").get_text().strip()
            except AttributeError:
                continue
            if row_name == "内容量":
                try:
                    ml = int("".join(c for c in row_value if c in DIGITS))
                except ValueError:
                    raise NotABeerError
        image_url = "https://www.antenna-america.com" + page_soup.find("img", class_="item-image")["src"]
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
                for beer_page, url in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_page, url)
                    except NotABeerError:
                        continue
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://www.antenna-america.com/",
            image_url="https://www.antenna-america.com/img/cache/5c8b665f-0054-4741-94eb-1052c0a8b503.png",
            shipping_fee=990,
        )
