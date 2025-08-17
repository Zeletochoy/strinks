import logging
import time
from collections import deque
from datetime import timedelta
from typing import Any

import cloudscraper
from bs4 import BeautifulSoup, Tag
from sqlmodel import select

from ...db import get_db
from ...db.tables import Brewery
from ..utils import JST, now_jst
from .rank import best_match
from .structs import FlavorTag, RateLimitError, UntappdBeerResult

logger = logging.getLogger(__name__)

MAX_REQ_PER_HOUR = 1000
REQ_COOLDOWN = 5
BEER_CACHE_TIME = timedelta(days=30)
session = cloudscraper.create_scraper(allow_brotli=False)


class UntappdWeb:
    # Cache of Untappd country names
    _countries_cache: list[str] | None = None

    def __init__(self):
        self.last_request_timestamps: deque[float] = deque(maxlen=MAX_REQ_PER_HOUR)
        self.headers = {
            "Referer": "https://untappd.com/home",
            "User-Agent": "Mozilla/5.0 (Linux) Gecko/20100101 Firefox/81.0",
        }
        self.db = get_db()

    def __str__(self) -> str:
        return "UntappdWeb()"

    def __repr__(self) -> str:
        return str(self)

    def _get_countries(self) -> list[str]:
        """Get the list of countries, fetching from Untappd if not cached."""
        if UntappdWeb._countries_cache is None:
            try:
                logger.info("Fetching Untappd country list...")
                res = session.get("https://untappd.com/beer/top_rated", headers=self.headers)
                if res.status_code >= 300:
                    raise ValueError("Failed to fetch country list")

                soup = BeautifulSoup(res.text, "html.parser")
                sort_picker = soup.find("select", id="sort_picker")
                if not isinstance(sort_picker, Tag):
                    raise ValueError("Could not find country selector")

                countries = []
                for option in sort_picker.find_all("option"):
                    text = option.get_text().strip()
                    if text and text != "Show All Countries":
                        countries.append(text)

                if countries:
                    logger.info(f"Loaded {len(countries)} countries from Untappd")
                    # Sort by length descending for longest match first
                    UntappdWeb._countries_cache = sorted(countries, key=len, reverse=True)
                else:
                    raise ValueError("No countries found in selector")
            except Exception as e:
                logger.error(f"Error fetching country list: {e}")
                raise

        return UntappdWeb._countries_cache

    def rate_limit(self):
        while len(self.last_request_timestamps) >= MAX_REQ_PER_HOUR:
            time_since_oldest = time.monotonic() - self.last_request_timestamps[0]
            if time_since_oldest < 3600:
                time.sleep(3600 - time_since_oldest)
            self.last_request_timestamps.popleft()
        if self.last_request_timestamps:
            time_since_last = time.monotonic() - self.last_request_timestamps[-1]
            if time_since_last < REQ_COOLDOWN:
                time.sleep(REQ_COOLDOWN - time_since_last)
        self.last_request_timestamps.append(time.monotonic())

    def _get_brewery_info(self, brewery_name: str, brewery_url: str) -> dict[str, Any]:
        """Get brewery ID, country, city, and state.

        First tries to find the brewery by name in the database.
        If not found, fetches the brewery page to extract the information.

        Args:
            brewery_name: Name of the brewery
            brewery_url: URL to the brewery page on Untappd

        Returns:
            Dict with brewery_id, brewery_country, and optionally brewery_city, brewery_state
        """
        # First try to find brewery in database by name
        statement = select(Brewery).where(Brewery.name == brewery_name)
        existing_brewery = self.db.session.exec(statement).first()
        if existing_brewery:
            result = {
                "brewery_id": existing_brewery.brewery_id,
                "brewery_country": existing_brewery.country,
            }
            if existing_brewery.city:
                result["brewery_city"] = existing_brewery.city
            if existing_brewery.state:
                result["brewery_state"] = existing_brewery.state
            return result

        # If not found, fetch the brewery page
        self.rate_limit()
        try:
            res = session.get(f"https://untappd.com{brewery_url}", headers=self.headers)
            if res.status_code >= 300:
                raise RateLimitError()
            soup = BeautifulSoup(res.text, "html.parser")

            # Extract brewery ID from og:image meta tag
            # Pattern: https://untappd.akamaized.net/site/brewery_logos/brewery-4779_6b79b_hd.jpeg
            og_image = soup.find("meta", property="og:image")
            if not isinstance(og_image, Tag):
                raise ValueError(f"Could not find og:image meta tag for brewery {brewery_name}")

            image_url = og_image.get("content")
            if not isinstance(image_url, str):
                raise ValueError(f"og:image has no content for brewery {brewery_name}")

            # Extract brewery ID from the URL
            import re

            match = re.search(r"brewery-(\d+)_", image_url)
            if not match:
                raise ValueError(f"Could not extract brewery ID from image URL: {image_url}")
            brewery_id = int(match.group(1))

            # Extract location from the p tag under the brewery name
            # The location is in a p tag right after the h1 brewery name
            name_elem = soup.find("h1")
            if name_elem and name_elem.parent:
                # Find the p tags in the parent container
                for p in name_elem.parent.find_all("p"):
                    text = p.get_text().strip()
                    # Skip subsidiary info and brewery type
                    if text and not text.startswith("Subsidiary") and "Brewery" not in text:
                        # This should be the location line
                        # Match against known countries (sorted by length for longest match first)
                        countries = self._get_countries()
                        country_found = None
                        for country in countries:
                            if text.endswith(country):
                                country_found = country
                                break

                        if not country_found:
                            logger.warning(f"Could not match country in location: {text}")
                            raise ValueError(f"Could not match country in location: {text}")

                        # Extract city and state from the part before the country
                        location_without_country = text[: -len(country_found)].strip()
                        result = {
                            "brewery_id": brewery_id,
                            "brewery_country": country_found,
                        }

                        # Parse city and state if present
                        if "," in location_without_country:
                            parts = [p.strip() for p in location_without_country.split(",")]
                            if parts:
                                result["brewery_city"] = parts[0]
                                if len(parts) > 1:
                                    # The rest is the state/province
                                    result["brewery_state"] = ", ".join(parts[1:])
                        elif location_without_country:
                            # Just city, no state
                            result["brewery_city"] = location_without_country

                        # Save the brewery to database for future use
                        try:
                            with self.db.commit_or_rollback():
                                self.db.insert_brewery(
                                    brewery_id=brewery_id,
                                    image_url=image_url,  # We have this from og:image
                                    name=brewery_name,
                                    country=country_found,
                                    city=result.get("brewery_city"),
                                    state=result.get("brewery_state"),
                                    check_existence=True,
                                )
                                logger.debug(f"Saved brewery {brewery_name} (ID: {brewery_id}) to database")
                        except Exception as e:
                            # If we can't save, still return the result
                            logger.warning(f"Could not save brewery to database: {e}")

                        return result

            # If we can't find the location at all
            raise ValueError(f"Could not find location for brewery {brewery_name}")

        except Exception as e:
            logger.error(f"Failed to fetch brewery info for {brewery_name}: {e}")
            raise RateLimitError()

    def _item_to_beer(self, item: Tag) -> UntappdBeerResult:
        label = item.find("a", class_="label")
        if not isinstance(label, Tag):
            raise ValueError("Could not find beer label")

        href = label.get("href")
        if not isinstance(href, str):
            raise ValueError("Beer label has no href")

        img = label.find("img")
        if not isinstance(img, Tag):
            raise ValueError("Could not find beer image")
        img_src = img.get("src")
        if not isinstance(img_src, str):
            raise ValueError("Beer image has no src")

        name_elem = item.find("p", class_="name")
        if not isinstance(name_elem, Tag):
            raise ValueError("Could not find beer name")

        brewery_elem = item.find("p", class_="brewery")
        if not isinstance(brewery_elem, Tag):
            raise ValueError("Could not find brewery")

        brewery_link = brewery_elem.find("a")
        if not isinstance(brewery_link, Tag):
            raise ValueError("Could not find brewery link")
        brewery_url = brewery_link.get("href")
        if not isinstance(brewery_url, str):
            raise ValueError("Brewery link has no href")

        style_elem = item.find("p", class_="style")
        if not isinstance(style_elem, Tag):
            raise ValueError("Could not find style")

        abv_elem = item.find("p", class_="abv")
        if not isinstance(abv_elem, Tag):
            raise ValueError("Could not find ABV")

        ibu_elem = item.find("p", class_="ibu")
        if not isinstance(ibu_elem, Tag):
            raise ValueError("Could not find IBU")

        caps_elem = item.find("div", class_="caps")
        if not isinstance(caps_elem, Tag):
            raise ValueError("Could not find rating caps")
        rating_str = caps_elem.get("data-rating")
        if not isinstance(rating_str, str):
            raise ValueError("Rating caps has no data-rating")

        brewery_name = brewery_elem.get_text().strip()
        brewery_info = self._get_brewery_info(brewery_name, brewery_url)

        return UntappdBeerResult(
            beer_id=int(href.rsplit("/", 1)[-1]),
            image_url=img_src,
            name=name_elem.get_text().strip(),
            brewery=brewery_name,
            brewery_id=int(brewery_info["brewery_id"]),
            brewery_country=str(brewery_info["brewery_country"]),
            brewery_city=brewery_info.get("brewery_city"),
            brewery_state=brewery_info.get("brewery_state"),
            style=style_elem.get_text().strip(),
            abv=float(abv_elem.get_text().strip().split("%", 1)[0].replace("N/A", "nan")),
            ibu=float(ibu_elem.get_text().strip().split(" ", 1)[0].replace("N/A", "nan")),
            rating=float(rating_str),
        )

    def try_find_beer(self, query: str) -> UntappdBeerResult | None:
        self.rate_limit()
        try:
            logger.debug(f"Untappd query for '{query}'")
            res = session.get(
                "https://untappd.com/search",
                params={"q": query},
                headers=self.headers,
            )
            if res.status_code >= 300:
                raise RateLimitError()
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup("div", class_="beer-item")
            if not items:
                return None
            beers = []
            for item in items:
                try:
                    beer = self._item_to_beer(item)
                    beers.append(beer)
                except Exception as e:
                    # Skip beers where we can't get full info
                    logger.debug(f"Skipping beer due to error: {e}")
                    continue
            if not beers:
                return None
            best_idx = best_match(query, (f"{beer.brewery} {beer.name}" for beer in beers))
            best_beer: UntappdBeerResult | None = beers[best_idx]
        except Exception as e:
            logger.error(f"Unexpected exception in UntappdWeb.try_find_beer: {e}")
            raise RateLimitError()
        return best_beer

    def get_beer_from_id(self, beer_id: int) -> UntappdBeerResult:
        return self._get_beer_from_db(beer_id) or self._query_beer(beer_id)

    def _query_beer(self, beer_id: int) -> UntappdBeerResult:
        self.rate_limit()
        try:
            res = session.get(f"https://untappd.com/beer/{beer_id}", headers=self.headers)
            if res.status_code >= 300:
                raise RateLimitError()
            soup = BeautifulSoup(res.text, "html.parser")
            item = soup.find("div", class_="content")
            if not isinstance(item, Tag):
                raise KeyError(f"Beer with ID {beer_id} not found on untappd")
            # For individual beer pages, we need to extract brewery info differently
            brewery_elem = item.find("p", class_="brewery")
            if not isinstance(brewery_elem, Tag):
                raise KeyError(f"Could not find brewery for beer {beer_id}")

            brewery_link = brewery_elem.find("a")
            if not isinstance(brewery_link, Tag):
                raise KeyError(f"Could not find brewery link for beer {beer_id}")

            brewery_url = brewery_link.get("href")
            if not isinstance(brewery_url, str):
                raise KeyError(f"Brewery link has no href for beer {beer_id}")

            brewery_name = brewery_elem.get_text().strip()
            brewery_info = self._get_brewery_info(brewery_name, brewery_url)

            # Now get the rest of the beer info
            label = item.find("a", class_="label")
            if not isinstance(label, Tag):
                raise ValueError("Could not find beer label")

            img = label.find("img")
            if not isinstance(img, Tag):
                raise ValueError("Could not find beer image")
            img_src = img.get("src")
            if not isinstance(img_src, str):
                raise ValueError("Beer image has no src")

            name_elem = item.find("p", class_="name")
            if not isinstance(name_elem, Tag):
                raise ValueError("Could not find beer name")

            style_elem = item.find("p", class_="style")
            if not isinstance(style_elem, Tag):
                raise ValueError("Could not find style")

            abv_elem = item.find("p", class_="abv")
            if not isinstance(abv_elem, Tag):
                raise ValueError("Could not find ABV")

            ibu_elem = item.find("p", class_="ibu")
            if not isinstance(ibu_elem, Tag):
                raise ValueError("Could not find IBU")

            caps_elem = item.find("div", class_="caps")
            if not isinstance(caps_elem, Tag):
                raise ValueError("Could not find rating caps")
            rating_str = caps_elem.get("data-rating")
            if not isinstance(rating_str, str):
                raise ValueError("Rating caps has no data-rating")

            beer_result = UntappdBeerResult(
                beer_id=beer_id,
                image_url=img_src,
                name=name_elem.get_text().strip(),
                brewery=brewery_name,
                brewery_id=int(brewery_info["brewery_id"]),
                brewery_country=str(brewery_info["brewery_country"]),
                brewery_city=brewery_info.get("brewery_city"),
                brewery_state=brewery_info.get("brewery_state"),
                style=style_elem.get_text().strip(),
                abv=float(abv_elem.get_text().strip().split("%", 1)[0].replace("N/A", "nan")),
                ibu=float(ibu_elem.get_text().strip().split(" ", 1)[0].replace("N/A", "nan")),
                rating=float(rating_str),
            )
        except Exception:
            raise RateLimitError()
        return beer_result

    def _get_beer_from_db(self, beer_id: int) -> UntappdBeerResult | None:
        beer = self.db.get_beer(beer_id)
        if beer is None:
            return None
        # Handle both naive and aware datetimes for backward compatibility
        updated_at = beer.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=JST)
        if now_jst() - updated_at > BEER_CACHE_TIME:
            logger.debug(f"Updating {beer}...")
            return None
        return UntappdBeerResult(
            beer_id=beer.beer_id,
            image_url=beer.image_url,
            name=beer.name,
            brewery=beer.brewery_name,
            brewery_id=beer.brewery_id,
            brewery_country=beer.brewery_country,
            style=beer.style,
            abv=float(beer.abv or "nan"),
            ibu=float(beer.ibu or "nan"),
            rating=float(beer.rating or "nan"),
            tags={FlavorTag(assoc.tag.tag_id, assoc.tag.name, assoc.count) for assoc in beer.tags},
        )
