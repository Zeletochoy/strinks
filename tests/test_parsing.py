"""Tests for parsing utilities based on existing scraper patterns.

These tests cover ALL patterns found across all scrapers to ensure
the parsing utilities work correctly for every shop.
"""

from strinks.api.shops.parsing import (
    clean_beer_name,
    extract_brewery_beer,
    extract_brewery_from_description,
    is_beer_set,
    keep_until_japanese,
    normalize_numbers,
    parse_centiliters,
    parse_milliliters,
    parse_price,
    parse_volume_ml,
)


class TestMillilitersParsing:
    """Test cases based on actual patterns used in scrapers."""

    def test_parse_ml_simple(self):
        """Test simple ml patterns from various scrapers."""
        # From hopbuds.py: r"(\d{3,4})ml"
        assert parse_milliliters("350ml") == 350
        assert parse_milliliters("500ml") == 500
        assert parse_milliliters("1000ml") == 1000

        # Edge case: 2-digit ml (not common but should handle)
        assert parse_milliliters("50ml") == 50

        # From threefeet.py: r"([0-9]+)ml" with .lower()
        assert parse_milliliters("350ML") == 350
        assert parse_milliliters("500Ml") == 500
        assert parse_milliliters("BEER 330ML CAN") == 330

    def test_parse_ml_japanese(self):
        """Test Japanese ml patterns."""
        # From antenna.py, beerzilla.py, slopshop.py: r"([0-9０-９]+)(ml|ｍｌ)"
        assert parse_milliliters("350ml") == 350
        assert parse_milliliters("350ｍｌ") == 350
        assert parse_milliliters("３５０ml") == 350
        assert parse_milliliters("３５０ｍｌ") == 350

        # Mixed full/half width
        assert parse_milliliters("３50ml") == 350
        assert parse_milliliters("3５０ｍｌ") == 350

    def test_parse_ml_with_context(self):
        """Test ml extraction from longer text."""
        # From ichigo.py: r"容量:(\d+)ml"
        assert parse_milliliters("容量:350ml") == 350
        assert parse_milliliters("容量:500ml") == 500
        assert parse_milliliters("その他情報\n容量:330ml\n原材料") == 330

        # From chouseiya.py: r"/([0-9]+)ml"
        assert parse_milliliters("beer/350ml") == 350
        assert parse_milliliters("ipa/500ml") == 500
        assert parse_milliliters("brewery/beer/473ml can") == 473

        # From volta.py: r"【ML】[^0-9]*(\d+)"
        assert parse_milliliters("【ML】350") == 350
        assert parse_milliliters("【ML】 500") == 500
        assert parse_milliliters("【ML】：　３３０") == 330  # with full-width numbers

        # From drinkup.py: r"Volume (\d+)mL"
        assert parse_milliliters("Volume 350mL") == 350
        assert parse_milliliters("Volume 473mL") == 473

    def test_parse_ml_in_title(self):
        """Test ml extraction from product titles."""
        # From maruho.py: r"^([^ ]+) *([0-9]{3,4})ml */ *(.*)$"
        assert parse_milliliters("BrewDog 330ml / Punk IPA") == 330
        assert parse_milliliters("Brewery 500ml/BeerName") == 500
        assert parse_milliliters("Stone 355ml / IPA") == 355

        # Tricky: spaces around ml
        assert parse_milliliters("Beer 350 ml") == 350
        assert parse_milliliters("Beer　３３０ｍｌ　缶") == 330

        # From gbf.py: r"([0-9]+)ml" on desc.lower()
        assert parse_milliliters("Craft Beer 350ML Can") == 350

        # From slopshop.py: patterns like "bottle 350ml" or "can 350ml"
        assert parse_milliliters("IPA bottle 355ml") == 355
        assert parse_milliliters("Lager can 500ml") == 500
        assert parse_milliliters("bottle　３３０ｍｌ") == 330

    def test_parse_ml_not_found(self):
        """Test when ml is not found."""
        assert parse_milliliters("Just a beer name") is None
        assert parse_milliliters("Price: 1500 yen") is None
        assert parse_milliliters("") is None
        assert parse_milliliters("6 pack") is None
        assert parse_milliliters("alcohol 5.5%") is None

    def test_parse_ml_edge_cases(self):
        """Test edge cases from various scrapers."""
        # From ohtsuki.py: direct extraction from table cell "330ml"
        assert parse_milliliters("330ml") == 330
        assert parse_milliliters("750ml") == 750  # Belgian bottles

        # From craftbeers.py: text.endswith("ml")
        assert parse_milliliters("容量 350ml") == 350
        assert parse_milliliters("サイズ: 473ml") == 473

        # Multiple ml values - should get first one
        assert parse_milliliters("330ml bottle, 6x330ml pack") == 330


class TestCentilitersParsing:
    """Test centiliter to milliliter conversion (digtheline uses cl)."""

    def test_parse_cl_to_ml(self):
        """Test cl patterns from digtheline.py."""
        # digtheline: r"(\d{2,3}(?:[.]\d{1,2})?)cl$"
        assert parse_centiliters("33cl") == 330
        assert parse_centiliters("50cl") == 500
        assert parse_centiliters("75cl") == 750

        # With decimals
        assert parse_centiliters("33.3cl") == 333
        assert parse_centiliters("37.5cl") == 375

        # Edge case from digtheline: if ml < 100: ml *= 10
        assert parse_centiliters("33cl") == 330
        assert parse_centiliters("3.3cl") == 33  # mini bottle

    def test_parse_cl_in_context(self):
        """Test cl extraction from full text."""
        assert parse_centiliters("Beer Name 5.5% 33cl") == 330
        assert parse_centiliters("IPA 6.2% 50cl bottle") == 500
        assert parse_centiliters("33CL") == 330  # uppercase


class TestVolumeParsing:
    """Test generic volume parsing that handles both ml and cl."""

    def test_parse_volume_ml(self):
        """Test that parse_volume_ml handles both ml and cl."""
        # ml patterns
        assert parse_volume_ml("350ml") == 350
        assert parse_volume_ml("500ML") == 500

        # cl patterns
        assert parse_volume_ml("33cl") == 330
        assert parse_volume_ml("75cl") == 750

        # Should prefer ml over cl if both present
        assert parse_volume_ml("330ml (33cl)") == 330

        # Not found
        assert parse_volume_ml("Just a beer") is None


class TestPriceParsing:
    """Test price extraction patterns from scrapers."""

    def test_parse_price_simple(self):
        """Test simple price patterns."""
        # From various scrapers that use int() after cleaning
        assert parse_price("1500") == 1500
        assert parse_price("500") == 500
        assert parse_price("12345") == 12345

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

        # From various scrapers with tax calculation
        # ibrew.py: round(price * 1.1) suggests pre-tax prices
        assert parse_price("1000") == 1000  # We just parse, not calculate tax

    def test_parse_price_edge_cases(self):
        """Test edge cases from various scrapers."""
        # Multiple prices - should get first
        assert parse_price("¥1,500 (was ¥2,000)") == 1500

        # Price in description
        assert parse_price("価格: 1,980円") == 1980

        # No price found
        assert parse_price("Sold out") is None
        assert parse_price("") is None


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
        assert clean_beer_name("  Beer   Name  ") == "Beer Name"

    def test_clean_beer_name_special_patterns(self):
        """Test cleaning special patterns from various scrapers."""
        # From volta.py: re.sub(r"\s.\d\d?/\d\d?入荷予定.", "", title)
        assert clean_beer_name("Beer Name (1/15入荷予定)") == "Beer Name"

        # From volta.py: re.sub(r"\s*\[[^]]+\]\s*", "", title)
        assert clean_beer_name("Beer [Limited Edition]") == "Beer"
        assert clean_beer_name("[New] Beer Name [330ml]") == "Beer Name"

        # From ohtsuki.py: re.sub("( ?(大瓶|初期|Magnum|Jeroboam|alc[.].*))*$", "", raw_name)
        assert clean_beer_name("Beer Name 大瓶") == "Beer Name"
        assert clean_beer_name("Beer Magnum") == "Beer"
        assert clean_beer_name("Beer alc.5.5%") == "Beer"

        # From drinkup.py: title.endswith("セット") suggests set removal
        assert clean_beer_name("ビール6本セット") == "ビール6本セット"  # Not removed by clean_beer_name

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

        # No separator
        brewery, beer = extract_brewery_beer("JustBeerName")
        assert brewery is None
        assert beer is None

        # Multiple separators - should use first matching pattern
        brewery, beer = extract_brewery_beer("Brewery - Beer / Style")
        assert brewery == "Brewery"
        assert beer == "Beer / Style"

    def test_extract_brewery_from_japanese_patterns(self):
        """Test Japanese separator patterns."""
        # From volta.py: if "　" in title (full-width space)
        assert extract_brewery_beer("ブルワリー　ビール名")[1] == "ビール名"

        # Mixed patterns
        brewery, beer = extract_brewery_beer("Stone Brewing / Arrogant Bastard")
        assert brewery == "Stone Brewing"
        assert beer == "Arrogant Bastard"


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

        # From drinkup.py: title.endswith("セット")
        assert is_beer_set("ビールセット") is True
        assert is_beer_set("お試しセット") is True

        # Edge cases
        assert is_beer_set("6-Pack IPA") is True
        assert is_beer_set("Single Can") is False
        assert is_beer_set("Mixed Case") is True


class TestNumberNormalization:
    """Test full-width to half-width number conversion."""

    def test_normalize_numbers(self):
        """Test converting full-width numbers."""
        # Used in several scrapers with [0-9０-９] patterns
        assert normalize_numbers("３５０") == "350"
        assert normalize_numbers("５００ｍｌ") == "500ｍｌ"
        assert normalize_numbers("価格：１，５００円") == "価格：1，500円"
        assert normalize_numbers("Mixed３５０ml") == "Mixed350ml"
        assert normalize_numbers("０１２３４５６７８９") == "0123456789"


class TestBreweryExtraction:
    """Test brewery extraction from descriptions."""

    def test_extract_brewery_from_description(self):
        """Test extracting brewery from description text."""
        # From antenna.py: re.search(r"ブリュワリー：([^<]+)<", desc)
        assert extract_brewery_from_description("ブリュワリー：Stone Brewing<br>") == "stone brewing"
        assert extract_brewery_from_description("other text\nブリュワリー：Brewdog</p>") == "brewdog"

        # Not found
        assert extract_brewery_from_description("No brewery info here") is None
        assert extract_brewery_from_description("") is None

    def test_extract_brewery_from_various_formats(self):
        """Test brewery extraction from various formats."""
        # From drinkup.py: re.search("醸造所:.*/([^\n]*)", desc_text)
        desc = "醸造所: USA/Stone Brewing Co.\n"
        result = extract_brewery_from_description(desc) or ""
        assert "stone" in result.lower()  # Result is lowercased

        # From digtheline.py: uses metafield or tags.split("[", 1)[0]
        # This would be handled differently but tests the concept
        assert extract_brewery_from_description("ブリュワリー：Omnipollo<") == "omnipollo"


class TestKeepUntilJapanese:
    """Test keep_until_japanese utility from utils.py."""

    def test_keep_until_japanese(self):
        """Test extracting text until Japanese characters."""
        # From beerzilla.py usage
        assert keep_until_japanese("stone-ipa-ビール") == "stone-ipa-"
        assert keep_until_japanese("beer-name") == "beer-name"
        assert keep_until_japanese("ビール") == ""
        assert keep_until_japanese("test123あいう") == "test123"

        # Edge cases
        assert keep_until_japanese("") == ""
        assert keep_until_japanese("no-japanese-here") == "no-japanese-here"
