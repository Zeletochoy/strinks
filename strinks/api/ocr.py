from PIL import Image
from pytesseract import image_to_string


def ocr_image(image: Image) -> str:
    return image_to_string(image, lang="jpn+eng")
