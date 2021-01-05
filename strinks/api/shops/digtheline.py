import re
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


class DigTheLine(Shop):
    short_name = "digtheline"
    display_name = "Dig The Line"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 0
        while True:
            url = (
                "https://www.searchanise.com/getresults?api_key=9f4Z4f8b4y&q=&sortBy=collection_155521319017_position"
                f"&sortOrder=asc&restrictBy[snize_facet3]=In Stock&startIndex={40*i}&maxResults=40&items=true"
                "&pages=true&categories=true&suggestions=true&queryCorrection=true&suggestionsMaxResults=3"
                "&pageStartIndex=0&pagesMaxResults=20&categoryStartIndex=0&categoriesMaxResults=20&facets=true"
                f"&facetsShowUnavailableOptions=false&ResultsTitleStrings=2&ResultsDescriptionStrings=0&page={i+1}"
                "&collection=beer&output=json&_=1605691567140"
            )
            yield requests.get(url).json()
            i += 1

    def _iter_page_beers(self, page_json: dict) -> Iterator[dict]:
        empty = True
        for item in page_json["items"]:
            yield item
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, beer_item: dict) -> ShopBeer:
        title = beer_item["title"].lower()
        match = re.match(r"^(.*) \d{1,2}(?:[.]\d{1,2})?% (\d{2,3}(?:[.]\d{1,2})?)cl$", title)
        if match is None:
            raise NotABeerError
        beer_name = match.group(1)
        try:
            brewery_name = beer_item["metafield_a807e0d0c7ca5fbce69362d5e8e9e642"].lower()
        except KeyError:
            brewery_name = beer_item["tags"].split("[", 1)[0].lower()
        brewery_name = brewery_name.replace("brasserie ", "")
        ml = float(match.group(2))
        if ml < 100:
            ml *= 10
        ml = int(ml)
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

    def iter_beers(self) -> Iterator[ShopBeer]:
        for listing_page in self._iter_pages():
            try:
                for beer_item in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_item)
                    except NotABeerError:
                        continue
            except NoBeersError:
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://dig-the-line-store.com/",
            image_url="https://shinpuhkan.jp/en/wp-content/uploads/sites/2/2020/03/gourmet_img_digtheline01.jpg",
            shipping_fee=1210,
        )
