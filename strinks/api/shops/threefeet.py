from collections.abc import AsyncIterator

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_json
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters


class Threefeet(Shop):
    short_name = "3feet"
    display_name = "Threefeet"

    async def _iter_pages(self) -> AsyncIterator[dict]:
        i = 1
        while True:
            # Removed category filter as it was returning no results
            url = (
                "https://cdn5.editmysite.com/app/store/api/v23/editor/users/139134080/sites/763710076392842546/"
                f"products?page={i}&per_page=180&sort_by=created_date&sort_order=desc"
                "&include=images,media_files,discounts&excluded_fulfillment=dine_in"
            )
            yield await fetch_json(self.session, url)
            i += 1

    async def _iter_page_beers(self, page_json: dict) -> AsyncIterator[dict]:
        beers = page_json["data"]
        if not beers:
            raise NoBeersError
        for beer in beers:
            yield beer

    def _parse_beer_page(self, page_json) -> ShopBeer:
        raw_name = page_json["permalink"].lower().replace("-", " ")
        price = page_json["price"]["high"]
        image_url = page_json["images"]["data"][0]["absolute_url"]
        url = "https://3feet.bansha9.com" + page_json["site_link"]

        # Volume is now in short_description field as HTML
        short_desc = page_json.get("short_description", "")

        # Use parsing utility for milliliters - check both short_description and seo_page_description
        ml = parse_milliliters(short_desc)
        if ml is None:
            # Fallback to seo_page_description
            desc = page_json.get("seo_page_description", "")
            ml = parse_milliliters(desc)
        if ml is None:
            raise NotABeerError

        return ShopBeer(
            raw_name=raw_name,
            url=url,
            milliliters=ml,
            price=price,
            quantity=1,
            image_url=image_url,
        )

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        async for listing_page in self._iter_pages():
            try:
                async for beer_json in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_json)
                    except NotABeerError:
                        continue
                    except Exception:
                        self.logger.exception("Error parsing page")
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
