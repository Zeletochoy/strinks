import logging
import re
from collections.abc import AsyncIterator
from csv import DictReader
from io import BytesIO
from time import time

import aiohttp
from bs4 import BeautifulSoup
from openai import BadRequestError
from PIL import Image

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..async_utils import fetch_bytes
from ..chatgpt import ChatGPTConversation
from . import Shop, ShopBeer

LIST_URL = "https://www.craftbeermarket.jp/todays-beer-list"
UNSUPPORTED_LOCATIONS = {"yakinicraft-kanda"}
CSV_HEADER = ("brewery", "beer", "abv", "size", "price")
SYSTEM_PROMPT = f"""
You are CBMGPT, an expert in reading Japanese craft beer menus and turning them into an usable format.
When given an image of the menu and an OCR transcript,  output the brewery name, beer name, alcohol by volume (ABV),
pour size in mL and price of that size for each beer in CSV format.
Only use the OCR output as a reference for spelling, the structure in the image is more important.
The beers rows are the ones prefixed by a number specifying their alcohol by volume.
Ignore other drinks like wine or cocktails as well as category titles that are underlined.
The beers are organized in categories by style, such as "FRUIT, SPICE BEER" or "WHITE BEER, WEIZEN" and underlined in
the image.
Text in a different color in the title such as a red "New!" is not part of the title and should be ignored.
The base prices and pour sizes are at the top of the page, some categories have overrides in their title and some beers
have special pricing or volumes overriding all these.
For example, if you see "(グラス:250mL,パイント:500mL)" you should use 500 as the size and report the price for a pint,
if you see "(100mL:￥400,200mL:￥700) you should use 200 as the size and 700 as the price.
If a beer has a line like "SPECIAL KEG グラス:￥1000, パイント:￥1500" under it, the size would be 473 (default pint)
and the price 1500.
All prices are in JPY.
The brewery name is specified before the beer name for each beer.
Sometimes the brewery's prefecture is included, usually between parentheses like "(東京)", this is not part of the
brewery or beer name so don't include it, same for styles between square brackets like "[Hazy IPA]".
Make sure to list all the available beers in the order they appear in the image, top to bottom and left column first.
All columns must be filled for each row, if all the information is not present ignore that beer.
Make sure to pay attention to price and quantity overrides from category headers and notes below the beer.
Make sure to output the brewery and beer names exactly as they appear on the menu, names are often play on words so
don't try to correct them. If unsure use the OCR output as reference.
If multiple sizes are available provide the biggest one.
Don't include units.
The first line must be the CSV header: "{",".join(CSV_HEADER)}".
Don't add any extra formatting, just output a valid CSV file.
"""


logger = logging.getLogger(__name__)


class CBM(Shop):
    short_name = "cbm"
    _menu_map_cache: dict[str, str] | None = None

    @classmethod
    async def get_locations(cls, session: aiohttp.ClientSession) -> list[str]:
        html = await fetch_bytes(session, LIST_URL)
        soup = BeautifulSoup(html, "html.parser")
        divs = soup.find_all("div", class_="half")
        return [div["id"] for div in divs if div.get("id") and div["id"] not in UNSUPPORTED_LOCATIONS]

    @classmethod
    async def _get_menu_map(cls, session: aiohttp.ClientSession) -> dict[str, str]:
        """Get mapping of location IDs to menu filenames, cached."""
        if cls._menu_map_cache is not None:
            return cls._menu_map_cache

        html = await fetch_bytes(session, LIST_URL)
        soup = BeautifulSoup(html, "html.parser")

        # Map location IDs to their menu filenames
        location_menu_map = {}

        # Find all location divs to get the order
        locations = soup.find_all("div", class_="half")
        location_ids = [loc.get("id") for loc in locations if loc.get("id")]

        # Find all script tags with menu URLs
        scripts = soup.find_all("script")
        script_index = 0

        for script in scripts:
            if script.string and "todaysmenu" in script.string:
                # Extract the menu URL from the script
                match = re.search(r"todaysmenu/([^\"]+\.jpg)", script.string)
                if match and script_index < len(location_ids):
                    menu_filename = match.group(1).replace(".jpg", "")
                    location_id = location_ids[script_index]
                    location_menu_map[location_id] = menu_filename
                    script_index += 1

        cls._menu_map_cache = location_menu_map
        return location_menu_map

    def __init__(self, session: aiohttp.ClientSession, location: str, timestamp: int | None = None):
        super().__init__(session)
        self.location = location
        self.timestamp = timestamp if timestamp is not None else int(time())
        self.display_name = f"Craft Beer Market {location}"

    async def _download_image(self) -> Image:
        data = await fetch_bytes(self.session, self.menu_url)
        return Image.open(BytesIO(data))

    async def iter_beers(self) -> AsyncIterator[ShopBeer]:
        # Get the menu URL with correct filename
        menu_map = await self._get_menu_map(self.session)
        menu_filename = menu_map.get(self.location, f"dm_{self.location}")
        self.menu_url = f"https://www.craftbeermarket.jp/todaysmenu/{menu_filename}.jpg?{self.timestamp}"

        try:
            gpt = ChatGPTConversation(SYSTEM_PROMPT)
            await gpt.send(text="Here's today's menu:", image_url=self.menu_url)
            image = await self._download_image()
            from ..ocr import ocr_image

            ocr_output = await ocr_image(image)
            gpt_csv = await gpt.send(
                f"This is the OCR transcript, use it to correct the names but keep all the beers:\n{ocr_output}"
            )
        except BadRequestError:
            logger.exception("OpenAI request error:")
            return
        gpt_csv = gpt_csv.strip("```").lstrip("csv").strip()  # common issue, wrap in ```csv
        reader = DictReader(gpt_csv.splitlines())
        if reader.fieldnames is None or set(reader.fieldnames) != set(CSV_HEADER):
            logger.error("Invalid CSV header from ChatGPT: %s", reader.fieldnames)
            return
        for beer in reader:
            try:
                beer_name = beer["beer"]
                brewery_name = beer["brewery"]
                # Skip if size or price can't be parsed as int
                size = int(beer["size"])
                price = int(beer["price"])
                yield ShopBeer(
                    raw_name=f"{brewery_name} {beer_name}",
                    url=self.menu_url,
                    brewery_name=brewery_name,
                    beer_name=beer_name,
                    milliliters=size,
                    price=price,
                    quantity=1,
                    image_url=self.menu_url,
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid beer data: {beer} - {e}")
                continue

    def get_db_entry(self, db: BeerDB) -> DBShop:
        image = "https://www.craftbeermarket.jp/wp2/wp-content/themes/cbm/images/common/logo_{self.location}.png"
        return db.insert_shop(
            name=f"{self.display_name} {self.location}",
            url=f"https://www.craftbeermarket.jp/todays-beer-list/#{self.location}",
            image_url=image,
            shipping_fee=0,
        )
