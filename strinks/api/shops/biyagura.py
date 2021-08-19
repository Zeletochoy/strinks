import re
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NotABeerError, Shop, ShopBeer


class Biyagura(Shop):
    short_name = "biyagura"
    display_name = "Biyagura"

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        for item in page_soup("div", class_="fs-c-productListItem__imageContainer"):
            url = "https://www.biyagura.jp" + item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        beer_name = page_soup.find("span", class_="fs-c-productNameHeading__name").get_text().strip()
        brewery_name = "Ise Kadoya"
        price = int(page_soup.find("span", class_="fs-c-price__value").get_text().strip().replace(",", ""))
        desc = page_soup.find("div", class_="p_box_left").get_text().strip().lower()
        ml_match = re.search(r"([0-9]+)ml", desc)
        if ml_match is None:
            raise NotABeerError
        ml = int(ml_match.group(1))
        image_url = page_soup.find("div", class_="fs-c-productMainImage__image").find("img")["src"]
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

    def iter_beers(self) -> Iterator[ShopBeer]:
        url = "https://www.biyagura.jp/c/all-items"
        page = requests.get(url).text
        soup = BeautifulSoup(page, "html.parser")
        for beer_page, url in self._iter_page_beers(soup):
            try:
                yield self._parse_beer_page(beer_page, url)
            except NotABeerError:
                continue
            except Exception as e:
                print(f"Unexpected exception while parsing page, skipping.\n{e}")

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://www.biyagura.jp/",
            image_url="https://isekadoyabeer.itembox.design/item/logo/h-logo-2.jpg?d=20201127133316",
            shipping_fee=920,
            free_shipping_over=11000,
        )
