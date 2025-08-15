from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter, Retry

JST = ZoneInfo("Asia/Tokyo")


def now_jst() -> datetime:
    """Get current datetime in JST timezone."""
    return datetime.now(tz=JST)


def get_retrying_session(max_retries=3) -> requests.Session:
    sess = requests.Session()

    retries = Retry(total=max_retries, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    sess.mount("http://", HTTPAdapter(max_retries=retries))
    sess.mount("https://", HTTPAdapter(max_retries=retries))

    return sess
