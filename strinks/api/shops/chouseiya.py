import re
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
        while True:
            url = f"https://beer-chouseiya.shop/shopbrand/all_items/page{i}"
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("div", class_="innerBox"):
            url = "https://beer-chouseiya.shop" + item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        if page_soup.find("p", class_="soldout") is not None:
            raise NotABeerError
        info = page_soup.find("div", id="itemInfo")
        title = info.find("h2").get_text().strip().lower()
        title_match = re.search(r"【(.*?)(?:\([^)]+\))?/(.*?)(?:\([^)]+\))?】", title)
        if title_match is None:
            raise NotABeerError
        beer_name = title_match.group(1)
        brewery_name = title_match.group(2)
        price_str = info.find("tr", id="M_usualValue").get_text().strip().lower()
        price_match = re.search(r"([0-9,]+)円", price_str)
        if price_match is None:
            raise NotABeerError
        price = int(price_match.group(1).replace(",", ""))
        desc = page_soup.find("div", class_="detailTxt").get_text().strip().lower()
        ml_match = re.search(r"/([0-9]+)ml", desc)
        if ml_match is None:
            raise NotABeerError
        ml = int(ml_match.group(1))
        image_href = page_soup.find("div", id="itemImg").find("a")["href"]
        image_match = re.search(r"imageview\('(.*)'\)", image_href)
        if image_match is None:
            raise NotABeerError
        image_url = "https://shop20-makeshop.akamaized.net/shopimages/chouseiya/" + image_match.group(1)
        try:
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
            url="https://beer-chouseiya.shop",
            image_url="https://shop20-makeshop.akamaized.net/shopimages/chouseiya/logo.png",
            shipping_fee=790,
            free_shipping_over=15000,
        )
