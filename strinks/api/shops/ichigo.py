import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer

DIGITS = set("0123456789")

session = get_retrying_session()


class IchiGoIchiAle(Shop):
    short_name = "ichigo"
    display_name = "Ichi Go Ichi Ale"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"https://151l.shop/?mode=grp&gid=1978037&sort=n&page={i}"
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[tuple[BeautifulSoup, str]]:
        empty = True
        for item in page_soup("li", class_="productlist_list"):
            if item.find("span", class_="item_soldout") is not None:
                continue
            url = "https://151l.shop/" + item.find("a")["href"]
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find("h2", class_="product_name").get_text().strip()
        name_match = re.search(r"[(（]([^）)]*)[）)]$", title)
        if name_match is None:
            raise NotABeerError
        raw_name = name_match.group(1).strip()
        price_text = page_soup.find("span", class_="product_price").get_text().strip()
        price_match = re.search(r"税込([0-9,]+)円", price_text)
        if price_match is None:
            raise NotABeerError
        price = int(price_match.group(1).replace(",", ""))
        desc = page_soup.find("div", class_="product_explain").get_text()
        ml_match = re.search(r"容量:(\d+)ml", desc.lower())
        if ml_match is None:
            raise NotABeerError
        ml = int(ml_match.group(1))
        image_url = page_soup.find("img", class_="product_img_main_img")["src"]
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
            name=self.display_name,
            url="https://151l.shop/",
            image_url="https://img21.shop-pro.jp/PA01423/875/PA01423875.png?cmsp_timestamp=20201017123822",
            shipping_fee=950,
        )
