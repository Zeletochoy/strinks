from datetime import date
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NotABeerError, Shop, ShopBeer


class IBrew(Shop):
    short_name = "ibrew"
    display_name = "IBrew"

    def __init__(self, location="ebisu", day=None):
        if day is None:
            day = date.today()
        self.location = location
        self.url = (
            f"https://craftbeerbar-ibrew.com/{location}-menu/beermenu/"
            f"{day.year}%e5%b9%b4{day.month}%e6%9c%88{day.day}%e6%97%a5"
            "-%e3%83%93%e3%83%bc%e3%83%ab%e3%83%a1%e3%83%8b%e3%83%a5%e3%83%bc/"
        )

    def _parse_beer_group(self, group_soup: BeautifulSoup, prices: Tuple[int, int]) -> Iterator[ShopBeer]:
        for beer_soup in group_soup.find_all("div", class_="beer-item"):
            if "tap-blew" in beer_soup.get("class"):
                continue  # sold out
            yield from self._parse_beer(beer_soup, prices)

    def _parse_beer(self, beer_soup: BeautifulSoup, prices: Tuple[int, int]) -> Iterator[ShopBeer]:
        brewery_name = beer_soup.find("div", class_="brewer").get_text().strip()
        beer_name = beer_soup.find("div", class_="beer").get_text().strip()
        image_url = beer_soup.find("figure").find("img")["src"]
        for ml, price in zip((270, 470), prices):
            yield ShopBeer(
                raw_name=f"{brewery_name} {beer_name}",
                url=self.url,
                brewery_name=brewery_name,
                beer_name=beer_name,
                milliliters=ml,
                price=price,
                quantity=1,
                image_url=image_url,
            )

    def iter_beers(self) -> Iterator[ShopBeer]:
        page = requests.get(self.url).text
        soup = BeautifulSoup(page, "html.parser")
        for group_soup, prices in (
            (soup.find("div", class_="limited-part"), (760, 1090)),
            (soup.find("div", class_="basic-part"), (430, 760)),
        ):
            try:
                yield from self._parse_beer_group(group_soup, prices)
            except NotABeerError:
                continue
            except Exception as e:
                print(f"Unexpected exception while parsing page, skipping.\n{e}")

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://craftbeerbar-ibrew.com//",
            image_url="https://craftbeerbar-ibrew.com/wp-content/themes/ib2/library/img/logo.png",
            shipping_fee=0,
        )
