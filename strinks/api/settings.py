import sys
from os import environ

from dotenv import load_dotenv

load_dotenv()

try:
    DEEPL_API_KEY = environ["DEEPL_API_KEY"]

    UNTAPPD_CLIENT_ID = environ["UNTAPPD_CLIENT_ID"]
    UNTAPPD_CLIENT_SECRET = environ["UNTAPPD_CLIENT_SECRET"]
except KeyError as e:
    print(f"Missing value for {e} in environment")
    sys.exit(1)
