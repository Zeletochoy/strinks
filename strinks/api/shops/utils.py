def keep_until_japanese(text: str) -> str:
    chars = []
    for c in text:
        if ord(c) < 0x3000:  # first japanese characters
            chars.append(c)
        else:
            break
    return "".join(chars)
