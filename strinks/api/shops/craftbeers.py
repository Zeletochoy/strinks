from collections.abc import Iterator

from bs4 import BeautifulSoup, Tag

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters, parse_price

session = get_retrying_session()


class CraftBeers(Shop):
    short_name = "craft"
    display_name = "Craft Beers"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://www.craftbeers.jp/view/category/all_items?page={i}&sort=order"
            yield BeautifulSoup(session.get(url).text, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[tuple[BeautifulSoup, str]]:
        items = page_soup.find("ul", class_="item-list")
        if not isinstance(items, Tag):
            raise NoBeersError
        for item in items("li"):
            url = "https://www.craftbeers.jp" + item.find("a")["href"]
            yield BeautifulSoup(session.get(url).text, "html.parser"), url

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        try:
            raw_name = page_soup.find("div", class_="item-title").get_text().strip().lower()
            image_url = page_soup.find("img", class_="item-image")["src"]
            if not image_url.startswith("https://"):
                image_url = "https://www.craftbeers.jp" + image_url
            table = page_soup.find("table", class_="detail-list")
            # Find the ml text from table
            ml_text = next(
                (row.get_text().strip() for row in table("td") if row.get_text().strip().lower().endswith("ml")), None
            )
            if ml_text is None:
                raise NotABeerError
            ml = parse_milliliters(ml_text)
            if ml is None:
                raise NotABeerError
            # Use parsing utility for price
            price_text = page_soup.find("span", {"data-id": "makeshop-item-price:1"}).get_text()
            price = parse_price(price_text)
            if price is None:
                raise NotABeerError
        except (AttributeError, StopIteration):
            raise NotABeerError
        return ShopBeer(
            raw_name=raw_name,
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
            name="Craft Beers",
            url="https://www.craftbeers.jp",
            image_url="https://www.craftbeers.jp/img/head_bg.jpg",
            shipping_fee=900,
        )
