"""Tests for parsing utilities based on existing scraper patterns."""

from strinks.api.shops.parsing import (
    clean_beer_name,
    extract_brewery_beer,
    is_beer_set,
    normalize_numbers,
    parse_milliliters,
    parse_price,
)


class TestMillilitersParsing:
    """Test cases based on actual patterns used in scrapers."""

    def test_parse_ml_simple(self):
        """Test simple ml patterns from various scrapers."""
        # From hopbuds.py: r"(\d{3,4})ml"
        assert parse_milliliters("350ml") == 350
        assert parse_milliliters("500ml") == 500
        assert parse_milliliters("1000ml") == 1000

        # From threefeet.py: r"([0-9]+)ml" with .lower()
        assert parse_milliliters("350ML") == 350
        assert parse_milliliters("500Ml") == 500

    def test_parse_ml_japanese(self):
        """Test Japanese ml patterns."""
        # From antenna.py, beerzilla.py, slopshop.py: r"([0-9０-９]+)(ml|ｍｌ)"
        assert parse_milliliters("350ml") == 350
        assert parse_milliliters("350ｍｌ") == 350
        assert parse_milliliters("３５０ml") == 350
        assert parse_milliliters("３５０ｍｌ") == 350

    def test_parse_ml_with_context(self):
        """Test ml extraction from longer text."""
        # From ichigo.py: r"容量:(\d+)ml"
        assert parse_milliliters("容量:350ml") == 350
        assert parse_milliliters("容量:500ml") == 500

        # From chouseiya.py: r"/([0-9]+)ml"
        assert parse_milliliters("beer/350ml") == 350
        assert parse_milliliters("ipa/500ml") == 500

        # From volta.py: r"【ML】[^0-9]*(\d+)"
        assert parse_milliliters("【ML】350") == 350
        assert parse_milliliters("【ML】 500") == 500

    def test_parse_ml_in_title(self):
        """Test ml extraction from product titles."""
        # From maruho.py: r"^([^ ]+) *([0-9]{3,4})ml */ *(.*)$"
        assert parse_milliliters("BrewDog 330ml / Punk IPA") == 330
        assert parse_milliliters("Brewery 500ml/BeerName") == 500

        # From gbf.py: r"([0-9]+)ml" on desc.lower()
        assert parse_milliliters("Craft Beer 350ML Can") == 350

    def test_parse_ml_not_found(self):
        """Test when ml is not found."""
        assert parse_milliliters("Just a beer name") is None
        assert parse_milliliters("Price: 1500 yen") is None
        assert parse_milliliters("") is None


class TestPriceParsing:
    """Test price extraction patterns from scrapers."""

    def test_parse_price_simple(self):
        """Test simple price patterns."""
        # From various scrapers that use int() after cleaning
        assert parse_price("1500") == 1500
        assert parse_price("500") == 500

    def test_parse_price_with_comma(self):
        """Test price with comma."""
        # From hopbuds.py, goodbeer.py, ichigo.py, chouseiya.py: .replace(",", "")
        assert parse_price("1,500") == 1500
        assert parse_price("10,000") == 10000

    def test_parse_price_with_yen(self):
        """Test price with yen symbol."""
        # From ohtsuki.py: .replace("円", "").replace(",", "")
        assert parse_price("1,500円") == 1500
        assert parse_price("500円") == 500

        # From hopbuds.py: .strip()[1:] suggests ¥ at start
        assert parse_price("¥1,500") == 1500
        assert parse_price("￥1,500") == 1500

    def test_parse_price_from_dict(self):
        """Test cases where price comes from JSON/dict."""
        # Many scrapers use page_json["offers"][0]["price"]
        # This would already be an int, so we test string conversion
        assert parse_price("1500") == 1500


class TestTextCleaning:
    """Test text cleaning patterns from scrapers."""

    def test_clean_beer_name_brackets(self):
        """Test removing brackets from beer names."""
        # From goodbeer.py, antenna.py: re.sub(r"【[^】]*】", "", title)
        assert clean_beer_name("【限定】ビール名") == "ビール名"
        assert clean_beer_name("ビール【500ml】") == "ビール"

        # Multiple brackets
        assert clean_beer_name("【新発売】【限定】ビール") == "ビール"

    def test_clean_beer_name_volume(self):
        """Test removing volume from beer names."""
        # From antenna.py: re.split(r"\([0-9０-９]+(ml|ｍｌ)\)", ...)[0]
        assert clean_beer_name("Beer Name (350ml)") == "Beer Name"
        assert clean_beer_name("Beer Name (350ｍｌ)") == "Beer Name"
        assert clean_beer_name("Beer Name (３５０ml)") == "Beer Name"

    def test_clean_beer_name_whitespace(self):
        """Test cleaning whitespace."""
        # From volta.py: .replace("\t", " ").replace("  ", " ")
        assert clean_beer_name("Beer\tName") == "Beer Name"
        assert clean_beer_name("Beer  Name") == "Beer Name"
        assert clean_beer_name("Beer\t\tName") == "Beer Name"

    def test_extract_brewery_beer_split(self):
        """Test extracting brewery and beer names."""
        # From hopbuds.py: title.lower().split(" - ")
        brewery, beer = extract_brewery_beer("Brewery Name - Beer Name")
        assert brewery == "Brewery Name"
        assert beer == "Beer Name"

        # From drinkup.py: title.split("／", 1)[-1]
        brewery, beer = extract_brewery_beer("Brewery／Beer Name")
        assert brewery == "Brewery"
        assert beer == "Beer Name"

        # From volta.py: title.rsplit("/", 1)[-1] suggests / separator
        brewery, beer = extract_brewery_beer("Brewery / Beer")
        assert brewery == "Brewery"
        assert beer == "Beer"


class TestQuantityParsing:
    """Test quantity/set detection patterns."""

    def test_is_set_detection(self):
        """Test detecting beer sets."""
        # From antenna.py: if "本セット" in raw_name
        assert is_beer_set("ビール 6本セット") is True
        assert is_beer_set("IPA 350ml") is False

        # From slopshop.py: split pattern suggests "bottle" or "can"
        assert is_beer_set("6 pack") is True
        assert is_beer_set("case of 12") is True


class TestNumberNormalization:
    """Test full-width to half-width number conversion."""

    def test_normalize_numbers(self):
        """Test converting full-width numbers."""
        # Used in several scrapers with [0-9０-９] patterns
        assert normalize_numbers("３５０") == "350"
        assert normalize_numbers("５００ｍｌ") == "500ｍｌ"
        assert normalize_numbers("価格：１，５００円") == "価格：1，500円"
        assert normalize_numbers("Mixed３５０ml") == "Mixed350ml"
