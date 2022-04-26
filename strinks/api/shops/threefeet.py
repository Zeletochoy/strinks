import re
from typing import Iterator

from ...db.models import BeerDB
from ..utils import get_retrying_session
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


session = get_retrying_session()


class Threefeet(Shop):
    short_name = "3feet"
    display_name = "Threefeet"

    def _iter_pages(self) -> Iterator[dict]:
        i = 1
        while True:
            url = (
                "https://cdn5.editmysite.com/app/store/api/v17/editor/users/139134080/sites/983958827989689969/"
                f"products?page={i}&per_page=180&sort_by=category_order&sort_order=asc&categories[]="
                "11ec1ebe1a8b6fc0b14a86224c9e9feb&include=images,media_files&in_stock=1&excluded_fulfillment=dine_in"
            )
            yield session.get(url).json()
            i += 1

    def _iter_page_beers(self, page_json: dict) -> Iterator[dict]:
        beers = page_json["data"]
        if not beers:
            raise NoBeersError
        yield from beers

    def _parse_beer_page(self, page_json) -> ShopBeer:
        raw_name = page_json["seo_page_title"].lower()
        price = page_json["price"]["high"]
        image_url = page_json["images"]["data"][0]["absolute_url"]
        url = "https://3feet.bansha9.com" + page_json["site_link"]
        desc = page_json["seo_page_description"]
        match = re.search(r"([0-9]+)ml", desc.lower())
        if match is not None:
            ml = int(match.group(1))
        try:
            return ShopBeer(
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
                for beer_json in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_json)
                    except NotABeerError:
                        continue
                    except Exception as e:
                        print(f"Unexpected exception while parsing page, skipping.\n{e}")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://3feet.bansha9.com/",
            image_url=(
                "https://3feet.bansha9.com/uploads/b/cc996f00-1564-11ec-ab98-6772a0ef448b/icon_180x180_ios_NDU4OD.png"
            ),
            shipping_fee=1340,
        )
