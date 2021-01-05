import re
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


class Cardinal(Shop):
    short_name = "cardinal"
    display_name = "Cardinal Trading"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://retail.cardinaltrading.jp/collections/beer?page={i}&sort_by=created-ascending"
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("div", class_="grid-product"):
            url = "https://retail.cardinaltrading.jp" + item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        brewery_name = page_soup.find("div", class_="product-single__vendor").get_text().strip().lower()
        if brewery_name == "westbrook brewing company":
            brewery_name = "westbrook brewing co"
        beer_name = page_soup.find("h1", class_="product-single__title").get_text().strip().lower()
        price_text = page_soup.find("span", class_="product__price").get_text().strip().lower()
        price = int(float(price_text[1:].replace(",", "")) * 1.1)
        qty_label = page_soup.find("label", class_="variant__button-label").get_text().strip().lower()
        ml = int(re.search(r"(\d{3,4})ml", qty_label).group(1))
        image_url = "https:" + page_soup.find("div", class_="product-image-main").find("img")["data-photoswipe-src"]
        try:
            return ShopBeer(
                brewery_name=brewery_name,
                beer_name=beer_name,
                raw_name=f"{brewery_name} {beer_name}",
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
            url="https://retail.cardinaltrading.jp/",
            image_url=(
                "https://cdn.shopify.com/s/files/1/0269/3677/0662/files/Cardinal_logo_circle"
                "withtext_transparent_1200x270_980f0ad8-f991-490f-991e-44e81b5fe23f_270x@2x.png?v=1587188532"
            ),
            shipping_fee=1234,  # ???
            free_shipping_over=5000,
        )
