"""Pizzakaya scraper for BeerMenus.com menu."""

import re
from collections.abc import AsyncIterator

from bs4 import BeautifulSoup, Tag

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_text
from . import NotABeerError, Shop, ShopBeer
from .parsing import parse_milliliters


class Pizzakaya(Shop):
    """Scraper for Pizzakaya beer menu on BeerMenus.com."""

    short_name = "pizzakaya"
    display_name = "Pizzakaya"
    menu_url = "https://www.beermenus.com/qr_menus/4106"

    def _parse_serving(self, serving_text: str) -> tuple[int, int]:
        """Parse serving text to extract volume and price.

        Format examples:
        - "300ml Draft ¥1200"
        - "355ml Bottle ¥1800"
        - "473ml Draft ¥1700"
        - "375ml Bottle ¥3100"

        Returns:
            Tuple of (milliliters, price_yen)
        """
        # Extract milliliters
        ml = parse_milliliters(serving_text)
        if not ml:
            raise NotABeerError(f"Could not parse volume from: {serving_text}")

        # Extract price - look specifically for yen symbol followed by digits
        price_match = re.search(r"¥(\d+)", serving_text)
        if not price_match:
            raise NotABeerError(f"Could not parse price from: {serving_text}")

        price = int(price_match.group(1))

        return ml, price

    def _parse_beer_item(self, item: Tag) -> ShopBeer | None:
        """Parse a beer item from the menu to extract the best value ShopBeer.

        Each beer can have multiple servings (different sizes).
        Returns the serving with the best price per ml.

        Args:
            item: BeautifulSoup Tag for a beer list item

        Returns:
            ShopBeer object with the best value, or None if no valid servings
        """
        servings: list[tuple[int, int]] = []  # List of (ml, price) tuples

        # Get beer name - handle tap number if present
        h3 = item.find("h3")
        if not h3:
            return None

        beer_name = h3.get_text(strip=True)

        # Remove tap number if present (e.g., "1." or "10.")
        beer_name = re.sub(r"^\d+\.\s*", "", beer_name)

        # Skip "Out" entries
        if beer_name.lower().startswith("out"):
            return None

        # Get brewery from location if available
        brewery_name = None
        caption = item.find("p", class_="caption")
        if caption and isinstance(caption, Tag):
            caption_text = caption.get_text(strip=True)
            # Extract brewery from location (after last middot)
            parts = caption_text.split("·")
            if len(parts) >= 3:
                # Last part is usually location like "Numazu, Shizuoka" or "Richmond, VA" or "Athens, OH"
                location = parts[-1].strip()
                # Extract the city part (before comma) as brewery location hint
                brewery_parts = location.split(",")
                if brewery_parts:
                    brewery_name = brewery_parts[0].strip()

        # Get servings
        servings_div = item.find("div", class_="beer-servings")
        if not servings_div or not isinstance(servings_div, Tag):
            return None

        # Parse each serving option and collect them
        for serving_p in servings_div.find_all("p", class_="caption"):
            if not isinstance(serving_p, Tag):
                continue

            serving_text = serving_p.get_text(strip=True)
            if not serving_text:
                continue

            try:
                ml, price = self._parse_serving(serving_text)
                servings.append((ml, price))

            except NotABeerError:
                self.logger.debug(f"Could not parse serving: {serving_text}")
                continue
            except Exception:
                self.logger.exception(f"Error parsing serving: {serving_text}")
                continue

        # No valid servings found
        if not servings:
            return None

        # Find the serving with the best price per ml
        best_ml, best_price = min(servings, key=lambda x: x[1] / x[0])

        # Create ShopBeer for the best value serving
        return ShopBeer(
            raw_name=beer_name,
            url=self.menu_url,
            milliliters=best_ml,
            price=best_price,
            quantity=1,
            beer_name=beer_name,
            brewery_name=brewery_name,
        )

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        """Fetch and parse all beers from the menu."""
        # Fetch the menu page
        page_html = await fetch_text(self.session, self.menu_url)
        soup = BeautifulSoup(page_html, "html.parser")

        # Find both on_tap and bottles sections
        sections = ["on_tap", "bottles"]

        for section_id in sections:
            section = soup.find("ul", id=section_id)
            if not section or not isinstance(section, Tag):
                self.logger.warning(f"Could not find section: {section_id}")
                continue

            # Parse each beer item in the section
            for item in section.find_all("li", class_="pure-list-item"):
                if not isinstance(item, Tag):
                    continue

                try:
                    beer = self._parse_beer_item(item)
                    if beer:
                        yield beer
                except Exception:
                    self.logger.exception("Error parsing beer item")
                    continue

    def get_db_entry(self, db: BeerDB) -> DBShop:
        """Get or create the database entry for this shop."""
        return db.insert_shop(
            name=self.display_name,
            url="https://www.instagram.com/pizzakaya",
            image_url="https://d2sochvv0rudri.cloudfront.net/qr_menus/4106/image_pizzakaya-78fe814e.jpeg",
            shipping_fee=0,  # Physical location, no shipping
        )
