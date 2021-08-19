import re
import time
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
            ts = int(time.time() * 1000)
            url = (
                f"https://services.mybcapps.com/bc-sf-filter/filter?t={ts}&sort=created-descending&_=pf"
                f"&shop=antenna-america-shop.myshopify.com&page={i}&limit=32&display=grid"
                "&collection_scope=226404991137&tag=&product_available=true&variant_available=true"
                "&build_filter_tree=true&check_cache=false&sort_first=available&locale=ja&event_type=history"
            )
            yield requests.get(url).json()
            i += 1

    def _iter_page_beers(self, page_json: dict) -> Iterator[dict]:
        empty = True
        for item in page_json["products"]:
            yield item
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, beer_item: dict) -> ShopBeer:
        brewery_name = beer_item["product_type"].lower()
        if not brewery_name:
            raise NotABeerError
        title = beer_item["title"].lower()[len(brewery_name) :]
        beer_name = title.split("/", 1)[0].strip()
        if "pack" in beer_item.get("vendor", "").lower():
            raise NotABeerError
        price = beer_item["price_min"]
        image_url = beer_item["images_info"][0]["src"]
        url = f"https://www.antenna-america.com/en/collections/all/products/{beer_item['handle']}"
        match = re.search(r"\((\d+)ml\)", title)
        if match is not None:
            ml = int(match.group(1))
            beer_name = beer_name[: -len(match.group(0)) - 1]
        else:
            page = requests.get(url).text
            soup = BeautifulSoup(page, features="html.parser")
            table = soup.find(id="PartsItemAttribute")
            if table is not None:
                for row in table("tr"):
                    try:
                        row_name = row.find("th").get_text().strip()
                        row_value = row.find("td").get_text().strip()
                    except AttributeError:
                        continue
                    if row_name == "内容量":
                        try:
                            ml = int("".join(c for c in row_value if c in DIGITS))
                            break
                        except ValueError:
                            raise NotABeerError
                else:
                    raise NotABeerError
            else:
                desc = soup.find("div", class_="product-single__description").get_text().lower()
                ml_match = re.search(r"(\d{3,4})ml", desc)
                if ml_match is None:
                    raise NotABeerError
                ml = int(ml_match.group(1))
        return ShopBeer(
            beer_name=beer_name,
            brewery_name=brewery_name,
            raw_name=brewery_name + " " + beer_name,
            url=url,
            milliliters=ml,
            price=price,
            quantity=1,
            image_url=image_url,
        )

    def iter_beers(self) -> Iterator[ShopBeer]:
        for listing_page in self._iter_pages():
            try:
                for beer_item in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_item)
                    except NotABeerError:
                        continue
                    except Exception as e:
                        print(f"Unexpected exception while parsing page, skipping.\n{e}")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://www.antenna-america.com/",
            image_url="https://www.antenna-america.com/img/cache/5c8b665f-0054-4741-94eb-1052c0a8b503.png",
            shipping_fee=990,
        )
