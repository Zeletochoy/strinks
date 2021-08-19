import re
from typing import Iterator, Tuple

import requests
from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from . import NotABeerError, Shop, ShopBeer


DIGITS = set("0123456789")


def keep_until_japanese(text: str) -> str:
    chars = []
    for c in text:
        if ord(c) < 0x3000:  # first japanese characters
            chars.append(c)
        else:
            break
    return "".join(chars)


class GoodBeerFaucets(Shop):
    short_name = "gbf"
    display_name = "Good Beer Faucets"

    def _iter_cat_pages(self, url_template: str) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = url_template.format(i)
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        for cat_page in (
            "https://gbfbottleshoppe.com/?mode=cate&cbid=2651706&csid=0&sort=n&page={}",  # imported
            "https://gbfbottleshoppe.com/?mode=cate&cbid=2657122&csid=0&sort=n&page={}",  # domestic
        ):
            for page in self._iter_cat_pages(cat_page):
                yield page
                if page.find("a", class_="icon_next") is None:
                    break

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        for item in page_soup("li", class_="prd_lst_unit"):
            if item.find("span", class_="prd_lst_soldout") is not None:
                continue
            url = "https://gbfbottleshoppe.com/" + item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser"), url

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find("h2", class_="ttl_h2").get_text()
        raw_name = keep_until_japanese(title).strip()
        table = page_soup.find("table", class_="product_spec_table")
        for row in table("tr"):
            try:
                row_name = row.find("th").get_text().strip()
                row_value = row.find("td").get_text().strip()
            except AttributeError:
                continue
            if row_name == "販売価格":
                try:
                    price = int("".join(c for c in row_value if c in DIGITS))
                except ValueError:
                    raise NotABeerError
        desc = page_soup.find("div", class_="product_exp").get_text().strip().split("\n", 1)[0]
        ml_match = re.search(r"([0-9]+)ml", desc.lower())
        if ml_match is None:
            raise NotABeerError
        ml = int(ml_match.group(1))
        image_url = page_soup.find("div", class_="product_image_main").find("img")["src"]
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
            for beer_page, url in self._iter_page_beers(listing_page):
                try:
                    yield self._parse_beer_page(beer_page, url)
                except NotABeerError:
                    continue
                except Exception as e:
                    print(f"Unexpected exception while parsing page, skipping.\n{e}")

    def get_db_entry(self, db: BeerDB) -> DBShop:
        return db.insert_shop(
            name=self.display_name,
            url="https://gbfbottleshoppe.com/",
            image_url="https://img21.shop-pro.jp/PA01456/392/PA01456392.jpg?cmsp_timestamp=20201016192055",
            shipping_fee=890,
        )
