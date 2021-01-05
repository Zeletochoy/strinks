from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


class Chouseiya(Shop):
    short_name = "chouseiya"
    display_name = "Chouseiya"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        params = {
            "mode": "",
            "category_id": "",
            "name": "",
            "disp_number": 50,
            "orderby": 2,
        }

        while True:
            url = "https://www.chouseiya-beer.com/products/list"
            page = requests.get(url, params={**params, "pageno": i}).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("div", class_="product_item"):
            url = item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find("h3", class_="item_name").get_text().strip()
        try:
            beer_name, brewery_name = title[1:].split("」", 1)
        except ValueError:
            raise NotABeerError
        beer_name = beer_name.split("※", 1)[0]
        brewery_name = brewery_name.split("※", 1)[0]
        price = int(page_soup.find("span", class_="price02_default").get_text().strip().replace(",", "")[len("¥ ") :])
        desc = page_soup.find(id="detail_not_stock_box__description_detail").get_text().strip()
        try:
            ml = int(desc.split("\n", 1)[0].rsplit("/", 1)[-1][: -len("ml")])
        except ValueError:
            raise NotABeerError
        image_src = page_soup.find(id="item_photo_area").find("img")["src"]
        image_url = f"https://www.chouseiya-beer.com{image_src}"
        try:
            return ShopBeer(
                raw_name=title,
                url=url,
                brewery_name=brewery_name,
                beer_name=beer_name,
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
            url="https://www.chouseiya-beer.com/",
            image_url="https://www.chouseiya-beer.com/html/template/default/img/common/header_logo.png",
            shipping_fee=900,
            free_shipping_over=10000,
        )
