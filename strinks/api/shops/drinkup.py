import re
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


class DrinkUp(Shop):
    short_name = "drinkup"
    display_name = "Drink Up"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://drinkuppers-ecshop.stores.jp/?page={i}"
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("a", class_="c-itemList__item-link"):
            url = "https://drinkuppers-ecshop.stores.jp" + item["href"]
            title = item.find("p", class_="c-itemList__item-name").get_text().strip()
            if title.endswith("セット"):  # skip sets
                continue
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find("h1", class_="item_name").get_text().strip()
        beer_name = title.split("／", 1)[-1]
        price_text = page_soup.find("p", class_="item_price").get_text()
        price = int(re.search(r"\d+", price_text.replace(",", "")).group(0))
        desc_text = page_soup.find("div", class_="main_content_result_item_list_detail").get_text()
        ml_match = re.search(r"Volume (\d+)mL", desc_text)
        ml = int(ml_match.group(1))
        brewery_match = re.search("醸造所:.*/([^\n]*)", desc_text)
        brewery_name = brewery_match.group(1)
        brewery_name = re.sub(r"( (Beer|Brewery) )?Co\.", "", brewery_name)
        raw_name = f"{brewery_name} {beer_name}"
        image_url = page_soup.find("div", class_="gallery_image_carousel").find("img")["src"]
        try:
            return ShopBeer(
                beer_name=beer_name,
                brewery_name=brewery_name,
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
                    except Exception as e:
                        print(f"Unexpected exception while parsing page, skipping.\n{e}")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name="Drink Up",
            url="https://drinkuppers-ecshop.stores.jp",
            image_url="https://p1-e6eeae93.imageflux.jp/c!/a=2,w=1880,u=0/drinkuppers-ecshop/5452ce0e2184264a81e3.png",
            shipping_fee=1100,
        )
