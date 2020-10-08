from typing import Iterator

import requests
from bs4 import BeautifulSoup

from . import NoBeersError, NotABeerError, Shop, ShopBeer


class Chouseiya(Shop):
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

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[BeautifulSoup]:
        empty = True
        for item in page_soup("div", class_="product_item"):
            url = item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup) -> ShopBeer:
        title = page_soup.find("h3", class_="item_name").get_text().strip()
        beer_name, brewery_name = title[1:].split("」", 1)
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
                for beer_page in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_page)
                    except NotABeerError:
                        continue
            except NoBeersError:
                break
