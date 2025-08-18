"""Craft Beer Online (beeronline.jp) scraper."""

import re
from collections.abc import Iterator

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session
from . import NotABeerError, Shop, ShopBeer
from .parsing import clean_beer_name, is_beer_set, parse_milliliters

session = get_retrying_session()


class CraftBeerOnline(Shop):
    """Craft Beer Online - Shopify-based craft beer store."""

    short_name = "craftbeeronline"
    display_name = "Craft Beer Online"

    def _fetch_products(self, page: int) -> dict:
        """Fetch products from the API."""
        # Using the API endpoint discovered via dev tools
        # Minimal params needed for the API to work
        url = (
            "https://services.mybcapps.com/bc-sf-filter/filter"
            f"?shop=riobrewing.myshopify.com"
            f"&page={page}"
            f"&limit=48"  # Larger limit to reduce requests
            f"&sort=created-descending"
            f"&locale=en"
            f"&handle=all"
        )

        response = session.get(url)
        result = response.json()
        assert isinstance(result, dict)
        return result

    def _parse_product(self, product: dict) -> ShopBeer:
        """Parse a product from the API response."""
        # Process items with product_category: "Beer" or "Uncategorized" (imported beers)
        category = product.get("product_category")
        if category not in ["Beer", "Uncategorized"]:
            raise NotABeerError

        # Get basic info
        title = product.get("title", "")
        handle = product.get("handle", "")

        # Skip non-beer items (merchandise, subscriptions, etc)
        non_beer_keywords = ["tray", "coaster", "barrunner", "subscription", "mug", "glass"]
        if any(keyword in handle.lower() for keyword in non_beer_keywords):
            raise NotABeerError

        # Skip numeric-only handles (likely errors)
        if handle.replace("-", "").isdigit():
            raise NotABeerError

        # Skip if it's a set
        if is_beer_set(title):
            raise NotABeerError

        # Get first variant (usually the only one for single beers)
        if not product.get("variants"):
            raise NotABeerError

        variant = product["variants"][0]

        # Parse price (comes as string like "690")
        price_str = variant.get("price", "0")
        try:
            price = int(float(price_str))
        except (ValueError, TypeError):
            raise NotABeerError

        if price == 0:
            raise NotABeerError

        # Skip unavailable items
        if not variant.get("available", False):
            raise NotABeerError

        # Build product URL
        url = f"https://beeronline.jp/products/{handle}"

        # Get image URL if available
        image_url = None
        images = product.get("images")
        if images and isinstance(images, list) and len(images) > 0:
            # Images come as relative URLs like "//cdn.shopify.com/..."
            img = images[0]
            if isinstance(img, str):
                if img.startswith("//"):
                    image_url = "https:" + img
                elif not img.startswith("http"):
                    image_url = "https://beeronline.jp" + img
                else:
                    image_url = img

        # Parse volume from title (e.g., "ビール名 330ml" or "Beer Name 330ml")
        milliliters = parse_milliliters(title)
        if milliliters is None:
            # Try to find volume in tags or description
            body_html = product.get("body_html", "")
            milliliters = parse_milliliters(body_html)

            if milliliters is None:
                # Default to 330ml if not found (common bottle size)
                milliliters = 330

        # Clean the handle to use as raw_name
        cleaned_handle = handle.replace("-", " ")
        # Remove everything after volume (ml or cl)
        cleaned_handle = re.sub(r"\s*\d+(?:ml|cl).*$", "", cleaned_handle, flags=re.IGNORECASE).strip()
        # Remove bottle/can/cans indicators
        cleaned_handle = re.sub(r"\b(bottle|bottles|can|cans)\b", "", cleaned_handle, flags=re.IGNORECASE).strip()
        # Clean up the name using existing utility
        cleaned_handle = clean_beer_name(cleaned_handle)

        return ShopBeer(
            raw_name=cleaned_handle,
            url=url,
            milliliters=milliliters,
            price=price,
            quantity=1,
            available=1,  # Only available items get here
            image_url=image_url,
        )

    def iter_beers(self) -> Iterator[ShopBeer]:
        """Iterate through all beers on Craft Beer Online."""
        page = 1
        seen_handles = set()

        while True:
            try:
                data = self._fetch_products(page)

                # Check if we have products
                products = data.get("products", [])
                if not products:
                    break

                for product in products:
                    handle = product.get("handle")
                    if handle in seen_handles:
                        continue
                    seen_handles.add(handle)

                    try:
                        yield self._parse_product(product)
                    except NotABeerError:
                        continue
                    except Exception as e:
                        print(f"Error parsing product: {e}")
                        continue

                # Check if we've reached the last page
                total_products = data.get("total_product", 0)
                if page * 48 >= total_products:
                    break

                page += 1

            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break

    def get_db_entry(self, db: BeerDB) -> DBShop:
        """Get or create database entry for this shop."""
        return db.insert_shop(
            name=self.display_name,
            url="https://beeronline.jp/",
            image_url="https://beeronline.jp/cdn/shop/files/craftbeeronline_logo_1656fe02-162a-483c-8852-4c165b4f0d85.png",
            shipping_fee=1210,
            free_shipping_over=11000,
        )
