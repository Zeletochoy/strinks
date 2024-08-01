import re
from typing import Iterator, Tuple

from bs4 import BeautifulSoup
from unidecode import unidecode

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer


session = get_retrying_session()


class Volta(Shop):
    short_name = "volta"
    display_name = "Beer Volta"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            #url = f"http://beervolta.com/?mode=srh&sort=n&cid=&keyword=&page={i}"
            url = f"https://beervolta.com/?mode=cate&cbid=2270431&csid=8&sort=n&page={i}"
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        content = page_soup.find("section", class_="l-content")
        items = content.find("div", class_="c-items")
        for item in items("a"):
            if item.find("div", class_="isSoldout") is not None:
                continue
            url = "http://beervolta.com/" + item["href"]
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        title = page_soup.find("h2", class_="c-product-name").get_text().strip()
        title = re.sub(r"\s.\d\d?/\d\d?入荷予定.", "", title)
        title = re.sub(r"\s*\[[^]]+\]\s*", "", title)
        if "　" in title:
            raw_name = title.rsplit("　", 1)[-1]
        elif "/" in title:
            raw_name = title.rsplit("/", 1)[-1]
        else:
            raw_name = title
        raw_name = raw_name.replace("\t", " ").replace("  ", " ").lower()
        price = int(page_soup.find("meta", property="product:price:amount")["content"])
        image_url = page_soup.find("meta", property="og:image")["content"]
        desc = page_soup.find("div", class_="c-message").get_text()
        for line in desc.split("\n"):
            if (match := re.search(r"【ML】[^0-9]*(\d+)", line)) is not None:
                ml = int(match.group(1))
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
            name="Beer Volta",
            url="http://beervolta.com/",
            image_url="http://img21.shop-pro.jp/PA01384/703/PA01384703.png?cmsp_timestamp=20201007154831",
            shipping_fee=999,
        )
