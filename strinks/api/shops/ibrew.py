from datetime import date, timedelta
from typing import Iterator

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import Shop, ShopBeer


session = get_retrying_session()


class IBrew(Shop):
    short_name = "ibrew"
    display_name = "IBrew"

    def __init__(self, location="ebisu", day=None):
        self.location = location
        if day is None:
            day = date.today()
        self.day = day
        self.prices = {}
        self._set_urls()

    def _set_urls(self) -> None:
        self.json_url = (
            f"https://craftbeerbar-ibrew.com/{self.location}-menu/wp-json/beer/v1/"
            f"graded_taps/{self.day.year}/{self.day.month}/{self.day.day}/"
        )
        self.html_url = (
            f"https://craftbeerbar-ibrew.com/{self.location}-menu/beermenu/"
            f"{self.day.year}年{self.day.month}月{self.day.day}日-ビールメニュー/"
        )

    def _get_grade_price(self, grade: str) -> int:
        return self.prices[grade[0]]

    def _set_grade_prices(self, api_json: dict) -> None:
        self.prices = {name[0]: grade["pint"] for name, grade in api_json["prices"].items() if name != "tax"}

    def _parse_beer(self, tap_json: dict) -> Iterator[ShopBeer]:
        brewery_name = tap_json.get("brewer")
        beer_name = tap_json.get("beer")
        image_url = tap_json.get("logo_url")
        if tap_json.get("special_price"):
            price = int(tap_json["special_price"])
        else:
            price = self._get_grade_price(tap_json["grade"])
        yield ShopBeer(
            raw_name=f"{brewery_name} {beer_name}",
            url=self.html_url,
            brewery_name=brewery_name,
            beer_name=beer_name,
            milliliters=470,
            price=int(round(price * 1.1)),  # tax
            quantity=1,
            image_url=image_url,
        )

    def iter_beers(self) -> Iterator[ShopBeer]:
        api_json = session.get(self.json_url).json()
        if not api_json["taps"]:  # no taplist yet, try previous day
            self.day -= timedelta(days=1)
            self._set_urls()
            api_json = session.get(self.json_url).json()
        self._set_grade_prices(api_json)
        taps = api_json.get("taps", {}).values()
        for tap in taps:
            if tap.get("status") != "ontap":
                continue
            try:
                yield from self._parse_beer(tap)
            except Exception as e:
                print(f"Unexpected exception while parsing page, skipping.\n{e}")

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://craftbeerbar-ibrew.com/",
            image_url="https://craftbeerbar-ibrew.com/wp-content/themes/ib2/library/img/logo.png",
            shipping_fee=0,
        )
