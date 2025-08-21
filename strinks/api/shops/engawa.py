"""Beer no Engawa scraper."""

import re
from collections.abc import AsyncIterator

from bs4 import BeautifulSoup

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import NoBeersError, Shop, ShopBeer
from .parsing import clean_beer_name, is_beer_set, parse_price


class BeerEngawa(Shop):
    """Beer no Engawa - Craft beer marketplace with direct brewery shipping."""

    short_name = "engawa"
    display_name = "Beer no Engawa"

    async def _iter_pages(self) -> AsyncIterator[BeautifulSoup]:
        """Iterate through all pages of beer listings.

        Filters to only show bottles (瓶) and cans (缶) - Cc1[0]=36&Cc1[1]=37
        """
        page_num = 1

        while True:
            # URL with filters for bottles (36) and cans (37) only
            url = f"https://beer-engawa.jp/products/all?Cc1%5B0%5D=36&Cc1%5B1%5D=37&exclusion=1&pageno={page_num}"

            try:
                response = await fetch_text(self.session, url)
                soup = BeautifulSoup(response, "html.parser")

                # Check if we have products on this page
                products = soup.select(".js-product-block")
                if not products:
                    break

                yield soup
                page_num += 1

            except Exception as e:
                self.logger.error(f"Error fetching page {url}: {e}")
                break

    async def _iter_page_beers(self, page_soup: BeautifulSoup) -> AsyncIterator[ShopBeer]:
        """Extract beer info from a page."""
        products = page_soup.select(".js-product-block")

        if not products:
            raise NoBeersError

        for product in products:
            try:
                # Get product link and ID
                link_elem = product.select_one("a[href*='/products/item/']")
                if not link_elem:
                    continue

                href = link_elem.get("href")
                # Ensure href is a string
                url = href if isinstance(href, str) else ""
                if url and not url.startswith("http"):
                    url = "https://beer-engawa.jp" + url
                if not url:
                    continue

                # Get product title
                title_elem = product.select_one("h3")
                if not title_elem:
                    continue
                raw_name = title_elem.get_text(strip=True)

                # Skip if it's a set/pack
                if is_beer_set(raw_name):
                    continue

                # Skip if it's a pump set or keg
                format_elem = product.select_one("li.p-pump-ranking__detail")
                if format_elem:
                    format_text = format_elem.get_text(strip=True)
                    if "樽" in format_text or "ポンプ" in format_text:
                        continue
                    # Only process if it's explicitly bottle or can
                    if "瓶" not in format_text and "缶" not in format_text:
                        continue

                # Get price - take the first price if there's a range
                price_elem = product.select_one(".p-pump-ranking__price")
                if not price_elem:
                    continue
                price_text = price_elem.get_text(strip=True)
                # Extract first price from "￥XXX ～ ￥YYY" or just "￥XXX"
                price_match = re.search(r"[¥￥]([0-9,]+)", price_text)
                if not price_match:
                    continue
                price = parse_price(price_match.group(1))
                if price is None:
                    continue

                # Get brewery info
                brewery_elem = product.select_one(".p-pump-ranking__user-name")
                brewery_name = brewery_elem.get_text(strip=True) if brewery_elem else None

                # Get image
                img_elem = product.select_one(".p-pump-ranking__img img")
                image_url = None
                if img_elem:
                    src = img_elem.get("src")
                    if src and isinstance(src, str):
                        image_url = "https://beer-engawa.jp" + src if not src.startswith("http") else src

                # Clean the beer name using existing utilities
                beer_name = clean_beer_name(raw_name)

                # If brewery name is in the beer name, extract just the beer part
                if brewery_name and beer_name.lower().startswith(brewery_name.lower()):
                    beer_name = beer_name[len(brewery_name) :].strip()
                    # Remove separator if present
                    beer_name = re.sub(r"^[-－・/／]\s*", "", beer_name)

                # Default to 330ml since volume is not shown on listing or detail pages
                milliliters = 330

                yield ShopBeer(
                    raw_name=raw_name,
                    url=url,
                    milliliters=milliliters,
                    price=price,
                    quantity=1,
                    available=1,
                    beer_name=beer_name,
                    brewery_name=brewery_name,
                    image_url=image_url,
                )

            except Exception as e:
                self.logger.error(f"Error parsing product: {e}")
                continue

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        """Iterate through all beers on Beer no Engawa."""
        seen_urls = set()

        async for listing_page in self._iter_pages():
            try:
                async for beer in self._iter_page_beers(listing_page):
                    # Skip if we've already seen this beer
                    if beer.url in seen_urls:
                        continue
                    seen_urls.add(beer.url)
                    yield beer

            except NoBeersError:
                # No beers on this page, continue to next
                continue

    def get_db_entry(self, db: BeerDB) -> DBShop:
        """Get or create database entry for this shop."""
        return db.insert_shop(
            name=self.display_name,
            url="https://beer-engawa.jp/",
            image_url="https://beer-engawa.jp/blog/wp-content/uploads/2024/08/beernoengawa_logo_jp.jpg",
            shipping_fee=1200,  # Varies by brewery and location, typical cost
        )
