import re
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NoBeersError, NotABeerError, Shop, ShopBeer


class CraftBeers(Shop):
    short_name = "craft"
    display_name = "Craft Beers"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        index = BeautifulSoup(requests.get("https://www.craftbeers.jp/").text, "html.parser")
        menu = index.find(id="categ")("div", class_="tabContainer")[1]
        for link in menu("a"):
            url = "https://www.craftbeers.jp" + link["href"]
            page = requests.get(url).content.decode("utf8")
            yield BeautifulSoup(page, "html.parser")

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("table", class_="t-box2"):
            url = "https://www.craftbeers.jp" + item.find("a")["href"]
            yield item, url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        try:
            raw_name = page_soup.find("a")["href"][1:].rstrip(".html").replace("-", " ").replace("_", " ")
            raw_name = re.sub(r" \d*can$", "", raw_name.lower())
            image_url = "https://www.craftbeers.jp" + page_soup.find("img")["src"]
            buy_box = page_soup.find("dl", class_="boxdl")
            desc = buy_box.find("dt").get_text().strip().lower()
            ml_match = re.search(r"(\d+)ml", desc)
            if ml_match is not None:
                ml = int(ml_match.group(1))
            price = int(buy_box.find("span", class_="bold").get_text().replace(",", "").replace("￥", ""))
        except AttributeError:
            raise NotABeerError
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
