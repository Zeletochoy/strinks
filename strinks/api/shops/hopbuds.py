import re
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


class HopBuds(Shop):
    short_name = "hopbuds"
    display_name = "Hop Buds"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://hopbudsnagoya.com/collections/craft-beers?page={i}"
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("a", class_="product-card"):
            if item.find("div", class_="product-card__availability"):
                continue  # Sold Out
            url = "https://hopbudsnagoya.com" + item["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find("h1", class_="product-single__title").get_text().strip()
        brewery_name, beer_name = title.lower().split(" - ")
        raw_name = f"{brewery_name} {beer_name}"
        price = int(page_soup.find(id="ProductPrice").get_text().strip()[1:].replace(",", ""))
        desc = page_soup.find("div", class_="rte").get_text().strip()
        ml = int(re.search(r"(\d{3,4})ml", desc).group(1))
        image_url = "https:" + page_soup.find(id="ProductPhotoImg")["src"]
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
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://hopbudsnagoya.com/",
            image_url="https://cdn.shopify.com/s/files/1/1097/0424/t/2/assets/logo.png?v=12514362392207784998",
            shipping_fee=850,
        )
