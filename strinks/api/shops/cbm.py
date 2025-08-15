import logging
from collections.abc import Iterator
from csv import DictReader
from io import BytesIO
from time import time

from bs4 import BeautifulSoup
from openai import BadRequestError
from PIL import Image

from ...db.models import BeerDB
from ...db.tables import Shop as DBShop
from ..chatgpt import ChatGPTConversation
from ..ocr import ocr_image
from ..utils import get_retrying_session
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
session = get_retrying_session()


class CBM(Shop):
    short_name = "cbm"
    display_name = "Craft Beer Market"

    @classmethod
    def get_locations(cls) -> list[str]:
        html = session.get(LIST_URL).content
        soup = BeautifulSoup(html, "html.parser")
        return [location for div in soup("div", class_="half") if (location := div["id"]) not in UNSUPPORTED_LOCATIONS]

    def __init__(self, location: str, timestamp: int | None = None):
        self.location = location
        if timestamp is None:
            timestamp = int(time())
        self.menu_url = f"https://www.craftbeermarket.jp/todaysmenu/dm_{location}.jpg?{timestamp}"

    def _download_image(self) -> Image:
        data = session.get(self.menu_url).content
        return Image.open(BytesIO(data))

    def iter_beers(self) -> Iterator[ShopBeer]:
        try:
            gpt = ChatGPTConversation(SYSTEM_PROMPT)
            gpt.send(text="Here's today's menu:", image_url=self.menu_url)
            ocr_output = ocr_image(self._download_image())
            gpt_csv = gpt.send(
                f"This is the OCR transcript, use it to correct the names but keep all the beers:\n{ocr_output}"
            )
        except BadRequestError:
            logger.exception("OpenAI request error:")
            return
        gpt_csv = gpt_csv.strip("```").lstrip("csv").strip()  # common issue, wrap in ```csv
        reader = DictReader(gpt_csv.splitlines())
        if reader.fieldnames is None or set(reader.fieldnames) != set(CSV_HEADER):
            logger.error(f"Invalid CSV header from ChatGPT: {reader.fieldnames}")
            return
        for beer in reader:
            beer_name = beer["beer"]
            brewery_name = beer["brewery"]
            yield ShopBeer(
                raw_name=f"{brewery_name} {beer_name}",
                url=self.menu_url,
                brewery_name=brewery_name,
                beer_name=beer_name,
                milliliters=int(beer["size"]),
                price=int(beer["price"]),
                quantity=1,
                image_url=self.menu_url,
            )

    def get_db_entry(self, db: BeerDB) -> DBShop:
        image = "https://www.craftbeermarket.jp/wp2/wp-content/themes/cbm/images/common/logo_{self.location}.png"
        return db.insert_shop(
            name=f"{self.display_name} {self.location}",
            url=f"https://www.craftbeermarket.jp/todays-beer-list/#{self.location}",
            image_url=image,
            shipping_fee=0,
        )
