import re
from collections.abc import AsyncIterator

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_json
from . import NoBeersError, NotABeerError, Shop, ShopBeer


class DigTheLine(Shop):
    short_name = "digtheline"
    display_name = "Dig The Line"

    async def _iter_pages(self) -> AsyncIterator[dict]:
        i = 0
        while True:
            url = (
                "https://www.searchanise.com/getresults?api_key=9f4Z4f8b4y&q=&sortBy=collection_155521319017_position"
                f"&sortOrder=asc&startIndex={40 * i}&maxResults=40&items=true"
                "&pages=true&categories=true&suggestions=true&queryCorrection=true&suggestionsMaxResults=3"
                "&pageStartIndex=0&pagesMaxResults=20&categoryStartIndex=0&categoriesMaxResults=20&facets=true"
                f"&facetsShowUnavailableOptions=false&ResultsTitleStrings=2&ResultsDescriptionStrings=0&page={i + 1}"
                "&collection=beer&output=json&_=1675839570448"
            )
            try:
                result = await fetch_json(self.session, url)
            except Exception as e:
                # API error or end of results - stop iteration
                self.logger.warning(f"Failed to fetch page {i + 1}: {e}")
                break
            yield result
            i += 1

    async def _iter_page_beers(self, page_json: dict) -> AsyncIterator[dict]:
        empty = True
        for item in page_json["items"]:
            if not item["quantity"]:
                continue
            yield item
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, beer_item: dict) -> ShopBeer:
        title = beer_item["title"].lower()
        # Updated pattern: now uses ml instead of cl
        match = re.match(r"^(.*) \d{1,2}(?:[.]\d{1,2})?% (\d{3,4})ml", title)
        if match is None:
            raise NotABeerError
        beer_name = match.group(1)
        try:
            brewery_name = beer_item["metafield_a807e0d0c7ca5fbce69362d5e8e9e642"].lower()
        except KeyError:
            brewery_name = beer_item["tags"].split("[", 1)[0].lower()
        brewery_name = brewery_name.replace("brasserie ", "")
        # Now directly in ml, no conversion needed
        ml = int(match.group(2))
        price = int(float(beer_item["price"]))
        return ShopBeer(
            beer_name=beer_name,
            brewery_name=brewery_name,
            raw_name=brewery_name + " " + beer_name,
            url=beer_item["link"],
            milliliters=ml,
            price=price,
            quantity=1,
            image_url=beer_item["image_link"],
        )

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        async for listing_page in self._iter_pages():
            try:
                async for beer_item in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_item)
                    except NotABeerError:
                        continue
                    except Exception:
                        self.logger.exception("Error parsing page")
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://dig-the-line-store.com/",
            image_url="https://cdn.shopify.com/s/files/1/0278/9189/2329/t/9/assets/logo.svg?v=2361053580776563633",
            shipping_fee=1210,
        )
