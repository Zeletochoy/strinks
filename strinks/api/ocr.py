import asyncio
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
from pytesseract import image_to_string

# Thread pool for CPU-bound OCR operations
_ocr_executor = ThreadPoolExecutor(max_workers=4)


async def ocr_image(image: Image) -> str:
    """Async OCR function that runs tesseract in a thread pool.

    Args:
        image: PIL Image to process

    Returns:
        Extracted text from the image
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_ocr_executor, image_to_string, image, "jpn+eng")
