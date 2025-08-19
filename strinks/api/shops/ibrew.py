import re
from collections.abc import Iterator
from datetime import timedelta

from bs4 import BeautifulSoup, Tag

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..utils import get_retrying_session, now_jst
from . import Shop, ShopBeer

session = get_retrying_session()


class IBrew(Shop):
    short_name = "ibrew"
    display_name = "IBrew"

    @classmethod
    def get_locations(cls) -> list[str]:
        """Get all IBrew locations for autodiscovery by scraping the homepage."""
        locations = []
        try:
            response = session.get("https://craftbeerbar-ibrew.com/")
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all tap-blog-wrapper divs that contain location info
            wrappers = soup.find_all("div", class_="tap-blog-wrapper")

            for wrapper in wrappers:
                # Get the blog link to extract location name
                blog_link = wrapper.find("a", href=re.compile(r"/blogs/"))
                if blog_link:
                    href = blog_link.get("href", "")
                    if isinstance(href, str) and "/blogs/" in href:
                        # Extract location from /blogs/location
                        location = href.split("/blogs/")[-1].strip("/")
                        if location and location != "news":  # Skip news blog
                            locations.append(location)

            return locations
        except Exception as e:
            print(f"Error fetching IBrew locations: {e}")
            # Fallback to known locations
            return ["ebisu", "ginza", "shinbashi", "akihabara", "yokohama"]

    @classmethod
    def _get_location_url(cls, location: str) -> str:
        """Get the tap list URL for a specific location by scraping the homepage."""
        try:
            response = session.get("https://craftbeerbar-ibrew.com/")
            soup = BeautifulSoup(response.text, "html.parser")

            # Find the tap-blog-wrapper that contains this location's blog link
            wrappers = soup.find_all("div", class_="tap-blog-wrapper")

            for wrapper in wrappers:
                blog_link = wrapper.find("a", href=f"/blogs/{location}")
                if blog_link:
                    # The tap list link should be the first link in the same wrapper
                    tap_link = wrapper.find("a")
                    if tap_link:
                        url = tap_link.get("href", "")
                        if isinstance(url, str) and url:
                            # Convert Google Sheets URLs to parseable format if needed
                            if "docs.google.com/spreadsheets" in url and "/pubhtml" in url:
                                # Parse gid from URL if present
                                gid_match = re.search(r"gid=(\d+)", url)
                                gid = gid_match.group(1) if gid_match else "0"

                                # Convert to /sheet format for parsing
                                base_url = url.split("/pubhtml")[0]
                                url = f"{base_url}/pubhtml/sheet?headers=false&gid={gid}"
                            return url

            # Special case for Ebisu which uses menu.craftbeerbar-ibrew.com
            if location == "ebisu":
                return f"https://menu.craftbeerbar-ibrew.com/{location}-menu/todays-beer/"

        except Exception as e:
            print(f"Error fetching URL for IBrew {location}: {e}")

        # Return empty string if not found
        return ""

    def __init__(self, location="ebisu", day=None):
        self.location = location

        # Get the tap list URL dynamically
        self.tap_list_url = self._get_location_url(location)
        if not self.tap_list_url:
            raise ValueError(f"Could not find tap list URL for IBrew location: {location}")

        # Check if this location uses the API (Ebisu) or Google Sheets
        self.is_api_based = "menu.craftbeerbar-ibrew.com" in self.tap_list_url

        if self.is_api_based:
            if day is None:
                day = now_jst().date()
            self.day = day
            self.prices: dict[str, int] = {}
            self._set_urls()

    def _set_urls(self) -> None:
        """Set API URL for Ebisu location."""
        if self.is_api_based:
            self.json_url = (
                f"https://menu.craftbeerbar-ibrew.com/{self.location}-menu/wp-json/beer/v1/"
                f"graded_taps/{self.day.year}/{self.day.month}/{self.day.day}/"
            )

    def _get_grade_price(self, grade: str) -> int:
        return self.prices[grade[0]]

    def _set_grade_prices(self, api_json: dict) -> None:
        self.prices = {name[0]: grade["pint"] for name, grade in api_json["prices"].items() if isinstance(grade, dict)}

    def _compute_price(self, tap_json: dict) -> int:
        price = self._get_grade_price(tap_json["grade"])
        for special_block in tap_json.get("special_price", "").split(","):
            if not special_block:
                continue
            type, extra = special_block.split(":")
            if type == "p":
                price += int(extra)
        return price

    def _parse_beer(self, tap_json: dict) -> Iterator[ShopBeer]:
        """Parse beer from API response (Ebisu only)."""
        brewery_name = tap_json.get("brewer")
        beer_name = tap_json.get("beer")
        image_url = tap_json.get("logo_url")
        price = self._compute_price(tap_json)
        yield ShopBeer(
            raw_name=f"{brewery_name} {beer_name}",
            url=self.tap_list_url,
            brewery_name=brewery_name,
            beer_name=beer_name,
            milliliters=470,
            price=round(price * 1.1),  # tax
            quantity=1,
            image_url=image_url,
        )

    def _clean_sheets_html(self, soup: BeautifulSoup) -> str:
        """Clean Google Sheets HTML to extract meaningful text for ChatGPT parsing."""
        # Find the main table
        table = soup.find("table", class_="waffle") or soup.find("table")
        if not table or not isinstance(table, Tag):
            return ""

        # Extract text from table rows, preserving structure
        cleaned_lines = []
        rows = table.find_all("tr")

        for row in rows:
            if not isinstance(row, Tag):
                continue

            # Get all cell texts in this row
            cells = row.find_all("td")
            row_texts = []

            for cell in cells:
                text = cell.get_text(strip=True)
                # Include all non-empty text to preserve beer numbers and prices
                if text:
                    row_texts.append(text)

            # Join cell texts with " | " to preserve structure
            if row_texts:
                line = " | ".join(row_texts)
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _parse_sheets_with_gpt(self, cleaned_text: str) -> Iterator[ShopBeer]:
        """Parse cleaned sheets text using ChatGPT."""
        import csv
        from io import StringIO

        from ..chatgpt import ChatGPTConversation

        system_prompt = """You are an expert at parsing Japanese craft beer tap lists from IBrew locations.

        IBrew tap lists have a specific structure:
        1. Category headers like "IBREW SPECIAL", "IBREW LIMITED", "IBREW EXTREME", "IBREW BASIC"
        2. Price rows immediately after category headers showing sizes and prices like:
           - "Half Pint ¥XXX(¥YYY) / Pint ¥ZZZ(¥WWW)" - standard format
           - Sometimes only Half Pint is available for certain beers
           - Rarely, special sizes like "Glass" or other volumes
           - The first price is pre-tax, the price in parentheses is WITH TAX (what customers pay)
        3. Beer entries with:
           - A number (1-100) in the first column
           - Brewery name (may be in same cell as beer or separate)
           - Beer name
           - Sometimes style, ABV%, and location information in subsequent cells/rows

        Important parsing rules:
        - Each numbered entry is a beer
        - The price that applies to a beer is the most recent price row ABOVE it
        - Get the LARGEST available size for each beer (usually Pint at 470ml, but if only Half Pint at 270ml is available, use that)
        - Always use the WITH TAX price (the number in parentheses)
        - Brewery names often contain: Brewing, Brewery, Beer, ブルワリー, 醸造, or are company names
        - Beer names are the specific product names, often contain style indicators (IPA, Lager, Stout, etc.)
        - If brewery and beer names are combined (e.g., "VERTERE Rostrata"), split them appropriately

        Name cleaning rules:
        - When names appear in both Japanese and English (e.g., "ゴーゼアネホGOSE ANEJO"), keep only the English version
        - Examples:
          * "ゴーゼアネホGOSE ANEJO" → "GOSE ANEJO"
          * "キュベソレイユCUVEE SOLEIL" → "CUVEE SOLEIL"
          * "インカ帝国Inca Empire" → "Inca Empire"
        - If only Japanese is available, keep the Japanese
        - Clean up brewery names the same way

        Output format: CSV with headers: brewery,beer,milliliters,price
        - brewery: The brewery/company name (cleaned as above)
        - beer: The specific beer name (cleaned as above)
        - milliliters: The volume in ml (470 for Pint, 270 for Half Pint, etc.)
        - price: The price WITH TAX for the largest available size

        Only include entries that have:
        1. A valid beer number (1-100)
        2. Both brewery AND beer name (not just one)
        3. A valid price from the category it belongs to

        Output ONLY the CSV data, no other text or markdown formatting."""

        try:
            gpt = ChatGPTConversation(system_prompt, model="gpt-5", temperature=1.0)
            response = gpt.send(f"Parse this IBrew {self.location} tap list:\n\n{cleaned_text}")

            # Clean up response
            response = response.strip("```").lstrip("csv").strip()

            # Parse CSV
            reader = csv.DictReader(StringIO(response))

            for row in reader:
                brewery = row.get("brewery", "").strip()
                beer = row.get("beer", "").strip()
                ml_str = row.get("milliliters", "").strip()
                price_str = row.get("price", "").strip()

                if not brewery or not beer:
                    continue

                # Parse milliliters
                try:
                    milliliters = int(re.sub(r"[^\d]", "", ml_str))
                    if milliliters <= 0 or milliliters > 1000:  # Sanity check
                        milliliters = 470  # Default to pint if invalid
                except (ValueError, AttributeError):
                    milliliters = 470  # Default to pint

                # Parse price
                try:
                    # Remove any non-numeric characters except digits
                    price = int(re.sub(r"[^\d]", "", price_str))
                    if price <= 0 or price > 10000:  # Sanity check
                        continue
                except (ValueError, AttributeError):
                    continue

                yield ShopBeer(
                    raw_name=f"{brewery} {beer}",
                    url=self.tap_list_url,
                    brewery_name=brewery,
                    beer_name=beer,
                    milliliters=milliliters,
                    price=price,
                    quantity=1,
                )

        except Exception as e:
            print(f"Error parsing IBrew {self.location} with ChatGPT: {e}")

    def iter_beers(self) -> Iterator[ShopBeer]:
        """Iterate through all beers for this IBrew location."""
        if self.is_api_based:
            # Use API for Ebisu
            api_json = session.get(self.json_url).json()
            if not api_json["taps"]:  # no taplist yet, try previous day
                self.day -= timedelta(days=1)
                self._set_urls()
                api_json = session.get(self.json_url).json()
            self._set_grade_prices(api_json)
            taps = api_json.get("taps", {}).values()
            for tap in taps:
                if tap.get("status") != "ontap":
                    continue
                try:
                    yield from self._parse_beer(tap)
                except Exception as e:
                    print(f"Unexpected exception while parsing page, skipping.\n{e}")
        else:
            # Use ChatGPT parsing for Google Sheets locations
            try:
                response = session.get(self.tap_list_url)
                soup = BeautifulSoup(response.text, "html.parser")

                # Clean the HTML to extract text
                cleaned_text = self._clean_sheets_html(soup)
                if not cleaned_text:
                    print(f"No content found for IBrew {self.location}")
                    return

                # Parse with ChatGPT
                yield from self._parse_sheets_with_gpt(cleaned_text)

            except Exception as e:
                print(f"Error fetching IBrew {self.location} sheet: {e}")

    def get_db_entry(self, db: BeerDB) -> DBShop:
        """Get or create database entry for this shop."""
        # Use location-specific display name if not Ebisu
        display_name = self.display_name if self.location == "ebisu" else f"IBrew {self.location.title()}"
        return db.insert_shop(
            name=display_name,
            url="https://craftbeerbar-ibrew.com/",
            image_url="https://craftbeerbar-ibrew.com/wp-content/themes/ib2/library/img/logo.png",
            shipping_fee=0,
        )
