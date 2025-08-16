import re
from collections.abc import Iterator

from bs4 import BeautifulSoup, Tag

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NoBeersError, NotABeerError, Shop, ShopBeer
from .parsing import clean_beer_name, extract_brewery_beer, parse_milliliters

session = get_retrying_session()


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

    def _iter_page_beers(self, page_soup: BeautifulSoup) -> Iterator[tuple[BeautifulSoup, str]]:
        empty = True
        content = page_soup.find("section", class_="l-content")
        if not isinstance(content, Tag):
            raise NoBeersError("Could not find content section")
        items = content.find("div", class_="c-items")
        if not isinstance(items, Tag):
            raise NoBeersError("Could not find items container")
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

        # Try to extract brewery/beer from title
        if "　" in title:
            raw_name = title.rsplit("　", 1)[-1]
        elif "/" in title:
            brewery, beer = extract_brewery_beer(title)
            raw_name = beer if beer else title
        else:
            raw_name = title

        # Clean the name
        raw_name = clean_beer_name(raw_name.lower())

        price = int(page_soup.find("meta", property="product:price:amount")["content"])
        image_url = page_soup.find("meta", property="og:image")["content"]
        desc = page_soup.find("div", class_="c-message").get_text()

        # Parse milliliters from description
        ml = parse_milliliters(desc)
        if ml is None:
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
            name="Beer Volta",
            url="http://beervolta.com/",
            image_url="http://img21.shop-pro.jp/PA01384/703/PA01384703.png?cmsp_timestamp=20201007154831",
            shipping_fee=999,
        )
