import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import Shop, ShopBeer

session = get_retrying_session()


class Ohtsuki(Shop):
    short_name = "ohtsuki"
    display_name = "Ohtsuki"

    def iter_beers(self) -> Iterator[ShopBeer]:
        base_url = "https://ohtsuki-saketen.com/beer/index.html"
        page_soup = BeautifulSoup(session.get(base_url).text, "html.parser")
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
                    raw_name = re.sub("( ?(大瓶|初期|Magnum|Jeroboam|alc[.].*))*$", "", raw_name)
                    ml = int(ml_cell.get_text().strip().replace("ml", ""))
                    price = int(price_cell.get_text().strip().replace("円", "").replace(",", ""))
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
