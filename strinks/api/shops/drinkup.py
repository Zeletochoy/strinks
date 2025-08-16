import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters, parse_price

session = get_retrying_session()


class DrinkUp(Shop):
    short_name = "drinkup"
    display_name = "Drink Up"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://drinkuppers-ecshop.stores.jp/?page={i}"
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("a", class_="c-itemList__item-link"):
            url = "https://drinkuppers-ecshop.stores.jp" + item["href"]
            title = item.find("p", class_="c-itemList__item-name").get_text().strip()
            if title.endswith("セット"):  # skip sets
                continue
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find("h1", class_="item_name").get_text().strip()
        beer_name = title.split("／", 1)[-1]
        price_text = page_soup.find("p", class_="item_price").get_text()
        # Use parsing utility for price
        price = parse_price(price_text)
        if price is None:
            raise NotABeerError

        desc_text = page_soup.find("div", class_="main_content_result_item_list_detail").get_text()
        # Use parsing utility for milliliters
        ml = parse_milliliters(desc_text)
        if ml is None:
            raise NotABeerError
        brewery_match = re.search("醸造所:.*/([^\n]*)", desc_text)
        if brewery_match is not None:
            brewery_name = brewery_match.group(1)
            brewery_name = re.sub(r"( (Beer|Brewery) )?Co\.", "", brewery_name)
            raw_name = f"{brewery_name} {beer_name}"
        image_url = page_soup.find("div", class_="gallery_image_carousel").find("img")["src"]
        return ShopBeer(
            beer_name=beer_name,
            brewery_name=brewery_name,
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
            name="Drink Up",
            url="https://drinkuppers-ecshop.stores.jp",
            image_url="https://p1-e6eeae93.imageflux.jp/c!/a=2,w=1880,u=0/drinkuppers-ecshop/5452ce0e2184264a81e3.png",
            shipping_fee=1100,
        )
