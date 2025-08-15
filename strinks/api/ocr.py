from PIL import Image
from pytesseract import image_to_string


def ocr_image(image: Image) -> str:
    result: str = image_to_string(image, lang="jpn+eng")
    return result
