from typing import Iterator

import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

from . import Backend, BackendBeer, NoBeersError, NotABeerError


class Volta(Backend):
    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"http://beervolta.com/?mode=srh&sort=n&cid=&keyword=&page={i}"
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[BeautifulSoup]:
        empty = True
        for item in page_soup("div", class_="item_box"):
            url = "http://beervolta.com/" + item.find("a")["href"]
            page = requests.get(url).text
            yield BeautifulSoup(page, "html.parser")
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup) -> BackendBeer:
        footstamp = page_soup.find("div", class_="footstamp")
        title = page_soup.find("h1", class_="product_name").get_text().strip()
        if "　" in title:
            raw_name = title.rsplit("　", 1)[-1]
        else:
            brewery_p = footstamp("p")[-1]
            brewery = unidecode(brewery_p("a")[-1].get_text().strip())
            raw_name = brewery + unidecode(title).rsplit(brewery, 1)[-1]
        raw_name = raw_name.replace("\t", " ").replace("  ", " ")
        cart_table = page_soup.find("table", class_="add_cart_table")
        for row in cart_table("tr"):
            try:
                row_name = row.find("th").get_text().strip()
                row_value = row.find("td").get_text().strip()
            except AttributeError:
                continue
            if row_name == "型番":
                try:
                    ml = int(row_value[1:])
                except ValueError:
                    raise NotABeerError
            elif row_name == "販売価格":
                price = int(row_value.rsplit("税込", 1)[-1][: -len("円)")].replace(",", ""))
        image_url = "http:" + page_soup.find(id="zoom1")["href"]
        try:
            return BackendBeer(
                raw_name=raw_name,
                milliliters=ml,
                price=price,
                quantity=1,
                image_url=image_url,
            )
        except UnboundLocalError:
            raise NotABeerError

    def iter_beers(self) -> Iterator[BackendBeer]:
        for listing_page in self._iter_pages():
            try:
                for beer_page in self._iter_page_beers(listing_page):
                    try:
                        yield self._parse_beer_page(beer_page)
                    except NotABeerError:
                        continue
            except NoBeersError:
                break
