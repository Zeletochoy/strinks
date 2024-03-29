import re
from typing import Iterator, Tuple, Optional
from urllib.parse import urlparse
from pathlib import Path

from bs4 import BeautifulSoup
from unidecode import unidecode

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer


session = get_retrying_session()


def _extract_untappd_beer_name(link_url: str) -> Optional[str]:
    if "untappd.com" not in link_url:
        return None
    path = Path(urlparse(link_url).path)
    if path.parts[:2] != ["/", "b"] or len(path.parts) < 3 :
        return None
    return path.parts[2].replace("-", " ")


class Volta(Shop):
    short_name = "volta"
    display_name = "Beer Volta"

    def _iter_pages(self) -> Iterator[BeautifulSoup]:
        i = 1
        while True:
            url = f"http://beervolta.com/?mode=srh&sort=n&cid=&keyword=&page={i}"
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser")
            i += 1

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[Tuple[BeautifulSoup, str]]:
        empty = True
        if (recently_viewed := page_soup.find("div", id="box_recentlychecked")) is not None:
            recently_viewed.decompose()
        for item in page_soup("div", class_="item_box"):
            if item.find("span", class_="sold_out") is not None:
                continue
            url = "http://beervolta.com/" + item.find("a")["href"]
            page = session.get(url).text
            yield BeautifulSoup(page, "html.parser"), url
            empty = False
        if empty:
            raise NoBeersError

    def _parse_beer_page(self, page_soup, url) -> ShopBeer:
        raw_name = None
        desc = page_soup.find("div", class_="product_description")
        if desc is not None:
            for link in desc("a"):
                if raw_name := _extract_untappd_beer_name(link.get("href", "")):
                    break
        if raw_name is None:
            footstamp = page_soup.find("div", class_="footstamp")
            title = page_soup.find("h1", class_="product_name").get_text().strip()
            title = re.sub(r"\s.\d\d?/\d\d?入荷予定.", "", title)
            title = re.sub(r"\s*\[[^]]+\]\s*", "", title)
            on_sale = any(link.get_text().strip() == "セール" for link in page_soup("a"))
            if on_sale:
                title = re.sub(r"^[^!]*!+ *", "", title)  # remove prefix like "SALE!!"
            if "　" in title:
                raw_name = title.rsplit("　", 1)[-1]
            elif "/" in title:
                raw_name = title.rsplit("/", 1)[-1]
            else:
                brewery_p = footstamp("p")[-1]
                brewery = unidecode(brewery_p("a")[-1].get_text().strip())
                raw_name = brewery + unidecode(title).rsplit(brewery, 1)[-1]
            raw_name = raw_name.replace("\t", " ").replace("  ", " ").lower()
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
        image_url = page_soup.find(id="zoom1")["href"]
        if not image_url.startswith("http"):
            image_url = "http:" + image_url
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
