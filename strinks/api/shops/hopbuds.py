from collections.abc import Iterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import extract_brewery_beer, parse_milliliters, parse_price

session = get_retrying_session()


class HopBuds(Shop):
    short_name = "hopbuds"
    display_name = "Hop Buds"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://hopbudsnagoya.com/collections/craft-beers?page={i}"
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("a", class_="product-card"):
            if item.find("div", class_="product-card__availability"):
                continue  # Sold Out
            url = "https://hopbudsnagoya.com" + item["href"]
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find("h1", class_="product-single__title").get_text().strip()

        # Extract brewery and beer name
        brewery_name, beer_name = extract_brewery_beer(title)
        if not brewery_name or not beer_name:
            # Fallback to original logic if extract_brewery_beer doesn't work
            brewery_name, beer_name = title.lower().split(" - ")
        else:
            brewery_name = brewery_name.lower()
            beer_name = beer_name.lower()

        raw_name = f"{brewery_name} {beer_name}"

        # Parse price
        price_text = page_soup.find(id="ProductPrice").get_text().strip()
        price = parse_price(price_text)
        if price is None:
            raise NotABeerError

        # Parse milliliters
        desc = page_soup.find("div", class_="rte").get_text().strip()
        ml = parse_milliliters(desc)
        if ml is None:
            raise NotABeerError

        image_url = "https:" + page_soup.find(id="ProductPhotoImg")["src"]

        return ShopBeer(
            raw_name=raw_name,
            brewery_name=brewery_name,
            beer_name=beer_name,
            url=url,
            milliliters=ml,
            price=price,
            quantity=1,
            image_url=image_url,
        )

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
            name=self.display_name,
            url="https://hopbudsnagoya.com/",
            image_url="https://cdn.shopify.com/s/files/1/1097/0424/t/2/assets/logo.png?v=12514362392207784998",
            shipping_fee=850,
        )
