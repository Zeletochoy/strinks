from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import Shop, ShopBeer
from .parsing import clean_beer_name, parse_milliliters, parse_price


class Ohtsuki(Shop):
    short_name = "ohtsuki"
    display_name = "Ohtsuki"

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        base_url = "https://ohtsuki-saketen.com/beer/index.html"
        page_soup = BeautifulSoup(await fetch_text(self.session, base_url), "html.parser")
        for table in page_soup("table", class_="product"):
            for row in table("tr"):
                try:
                    try:
                        name_cell, _, ml_cell, price_cell, avail_cell = row("td")
                    except ValueError:
                        continue
                    if avail_cell.get_text().strip() == "X":
                        continue  # Sold Out
                    url = base_url + name_cell.find("a")["href"]
                    image_url = base_url.replace(".html", ".jpg")
                    raw_name = name_cell.get_text("\n").lower().split("\n", 1)[0]
                    # Use parsing utility for cleaning
                    raw_name = clean_beer_name(raw_name)
                    # Use parsing utilities
                    ml = parse_milliliters(ml_cell.get_text().strip())
                    if ml is None:
                        continue
                    price = parse_price(price_cell.get_text().strip())
                    if price is None:
                        continue
                    yield ShopBeer(
                        raw_name=raw_name,
                        url=url,
                        milliliters=ml,
                        price=price,
                        quantity=1,
                        image_url=image_url,
                    )
                except Exception:
                    self.logger.exception("Error parsing page")

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="http://www.ohtsuki-saketen.com/",
            image_url="http://www.ohtsuki-saketen.com/columnpicture/kriek%20de%20ranke%20and%20others.jpg",
            shipping_fee=1140,
        )
