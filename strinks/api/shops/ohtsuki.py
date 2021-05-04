import re
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import Shop, ShopBeer


class Ohtsuki(Shop):
    short_name = "ohtsuki"
    display_name = "Ohtsuki"

    def iter_beers(self) -> Iterator[ShopBeer]:
        base_url = "http://www.ohtsuki-saketen.com/catalog/"
        page = requests.get(base_url).content.decode("sjis")
        page_soup = BeautifulSoup(page, "html.parser")
        for row in page_soup("tr"):
            try:
                try:
                    name_cell, ml_cell, price_cell, avail_cell = row("td")
                except ValueError:
                    continue
                if avail_cell.get_text().strip() == "X":
                    continue  # Sold Out
                url = base_url + name_cell.find("a")["href"]
                page = requests.get(url).text.replace("<br/>", "\n")
                beer_soup = BeautifulSoup(page, "html.parser")
                image_url = base_url + beer_soup.find("div", class_="img").find("img")["src"]
                raw_name = name_cell.get_text("\n").lower().split("\n", 1)[0]
                raw_name = re.sub("( ?(大瓶|初期|Magnum|Jeroboam|alc[.].*))*$", "", raw_name)
                ml = int(ml_cell.get_text().strip().replace("ml", ""))
                price = int(int(price_cell.get_text().strip().replace("円", "")) * 1.1)  # tax
                yield ShopBeer(
                    raw_name=raw_name,
                    url=url,
                    milliliters=ml,
                    price=price,
                    quantity=1,
                    image_url=image_url,
                )
            except Exception as e:
                print(f"Unexpected exception while parsing page, skipping.\n{e}")

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="http://www.ohtsuki-saketen.com/",
            image_url="http://www.ohtsuki-saketen.com/columnpicture/kriek%20de%20ranke%20and%20others.jpg",
            shipping_fee=1140,
        )
