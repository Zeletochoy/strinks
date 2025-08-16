"""Common parsing utilities for shop scrapers.

Based on actual patterns used across existing scrapers.
"""

import re


def keep_until_japanese(text: str) -> str:
    """Keep characters until first Japanese character.

    From utils.py, used by beerzilla.py.

    Args:
        text: Text to process

    Returns:
        Text up to but not including first Japanese character
    """
    chars = []
    for c in text:
        if ord(c) < 0x3000:  # first japanese characters
            chars.append(c)
        else:
            break
    return "".join(chars)


def normalize_numbers(text: str) -> str:
    """Convert full-width numbers to half-width.

    Used by scrapers that handle Japanese text with patterns like [0-9０-９].

    Args:
        text: Text potentially containing full-width numbers

    Returns:
        Text with normalized numbers
    """
    # Full-width to half-width conversion
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    return text.translate(trans)


def parse_milliliters(text: str) -> int | None:
    r"""Extract milliliters from text.

    Based on patterns from actual scrapers:
    - hopbuds: r"(\d{3,4})ml"
    - antenna/beerzilla/slopshop: r"([0-9０-９]+)(ml|ｍｌ)"
    - ichigo: r"容量:(\d+)ml"
    - chouseiya: r"/([0-9]+)ml"
    - volta: r"【ML】[^0-9]*(\d+)"
    - maruho: r"([0-9]{3,4})ml"

    Args:
        text: Text potentially containing volume information

    Returns:
        Volume in milliliters, or None if not found
    """
    # Normalize full-width numbers first
    text = normalize_numbers(text)
    text_lower = text.lower()

    # Try patterns from actual scrapers, ordered by specificity
    patterns = [
        r"容量:(\d+)ml",  # ichigo - specific format
        r"【ml】[^0-9]*(\d+)",  # volta - bracketed format
        r"Volume (\d+)mL",  # drinkup - English label
        r"/(\d+)ml",  # chouseiya - with slash
        r"(\d{3,4})ml",  # hopbuds, maruho - 3-4 digits
        r"(\d+)\s*ml",  # Allow space before ml
        r"(\d+)ml",  # threefeet, gbf - any digits
        r"(\d+)ｍｌ",  # Japanese ml
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return int(match.group(1))

    return None


def parse_centiliters(text: str) -> int | None:
    r"""Extract centiliters and convert to milliliters.

    From digtheline.py: r"(\d{2,3}(?:[.]\d{1,2})?)cl$"

    Args:
        text: Text potentially containing volume in cl

    Returns:
        Volume in milliliters, or None if not found
    """
    text_lower = text.lower()

    # Match cl patterns
    match = re.search(r"(\d{1,3}(?:[.]\d{1,2})?)cl", text_lower)
    if match:
        cl = float(match.group(1))
        ml = cl * 10
        # digtheline logic: if ml < 100: ml *= 10 (but this seems wrong for cl->ml)
        return int(ml)

    return None


def parse_volume_ml(text: str) -> int | None:
    """Parse volume from text, handling both ml and cl.

    Tries ml first, then cl.

    Args:
        text: Text potentially containing volume

    Returns:
        Volume in milliliters, or None if not found
    """
    # Try ml first
    ml = parse_milliliters(text)
    if ml is not None:
        return ml

    # Try cl
    return parse_centiliters(text)


def parse_price(text: str) -> int | None:
    """Extract price from text.

    Based on patterns from scrapers:
    - Many use .replace(",", "") to remove commas
    - ohtsuki uses .replace("円", "").replace(",", "")
    - hopbuds uses .strip()[1:] suggesting ¥ at start

    Args:
        text: Text potentially containing price

    Returns:
        Price as integer yen, or None if not found
    """
    # Remove common price markers (from various scrapers)
    text = text.replace(",", "")  # Most scrapers
    text = text.replace("円", "")  # ohtsuki
    text = text.replace("¥", "")  # Implied by hopbuds
    text = text.replace("￥", "")  # Full-width yen
    text = text.strip()

    # Extract first number
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))

    return None


def clean_beer_name(text: str) -> str:
    r"""Clean up beer name.

    Based on patterns from scrapers:
    - goodbeer/antenna: re.sub(r"【[^】]*】", "", title)
    - antenna: re.split(r"\([0-9０-９]+(ml|ｍｌ)\)", ...)[0]
    - volta: .replace("\t", " ").replace("  ", " ")
    - goodbeer: .replace("限定醸造", "")

    Args:
        text: Raw beer name

    Returns:
        Cleaned beer name
    """
    # Remove Japanese brackets (goodbeer, antenna)
    text = re.sub(r"【[^】]*】", "", text)

    # Remove square brackets (volta)
    text = re.sub(r"\s*\[[^]]+\]\s*", "", text)

    # Remove volume in parentheses (antenna pattern)
    text = re.split(r"\([0-9０-９]+(ml|ｍｌ)\)", text)[0]

    # Remove arrival date info (volta)
    text = re.sub(r"\s*\(\d\d?/\d\d?入荷予定\)", "", text)

    # Remove bottle size indicators (ohtsuki)
    text = re.sub(r"\s*(大瓶|初期|Magnum|Jeroboam|alc[.].*)*$", "", text)

    # Remove specific terms (goodbeer)
    text = text.replace("限定醸造", "")

    # Clean whitespace (volta pattern)
    text = text.replace("\t", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_brewery_beer(text: str) -> tuple[str | None, str | None]:
    """Extract brewery and beer name from a combined string.

    Based on patterns from scrapers:
    - hopbuds: split(" - ")
    - drinkup: split("／", 1)
    - volta: rsplit("/", 1)

    Args:
        text: Combined brewery and beer text

    Returns:
        Tuple of (brewery_name, beer_name), either can be None
    """
    # Try separators used in actual scrapers
    separators = [
        " - ",  # hopbuds
        "／",  # drinkup (full-width slash)
        " / ",  # Common pattern
        "/",  # volta
        "　",  # Full-width space (volta)
    ]

    for sep in separators:
        if sep in text:
            parts = text.split(sep, 1)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()

    # No clear separation found
    return None, None


def is_beer_set(text: str) -> bool:
    """Check if the text indicates a beer set/pack.

    Based on antenna.py: if "本セット" in raw_name

    Args:
        text: Text to check

    Returns:
        True if this appears to be a set/pack
    """
    text_lower = text.lower()

    # Indicators from actual scrapers
    set_indicators = [
        "本セット",  # antenna - Japanese "bottles set"
        "セット",  # drinkup - Japanese "set"
        "pack",  # Common English
        "case",  # Common English
    ]

    return any(indicator in text_lower for indicator in set_indicators)


def extract_brewery_from_description(text: str) -> str | None:
    """Extract brewery name from description text.

    Based on:
    - antenna.py: re.search(r"ブリュワリー：([^<]+)<", desc)
    - drinkup.py: re.search("醸造所:.*/([^\n]*)", desc_text)

    Args:
        text: Description text potentially containing brewery

    Returns:
        Brewery name or None
    """
    text_lower = text.lower()

    # antenna pattern for brewery in description
    match = re.search(r"ブリュワリー：([^<]+)<", text_lower)
    if match:
        return match.group(1).strip()

    # drinkup pattern for brewery
    match = re.search(r"醸造所:.*/([^\n]*)", text)
    if match:
        brewery = match.group(1).strip()
        # Remove common suffixes (from drinkup)
        brewery = re.sub(r"( (Beer|Brewery) )?Co\.", "", brewery)
        return brewery.lower() if brewery else None

    return None
