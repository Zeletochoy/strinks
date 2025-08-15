from ..settings import UNTAPPD_CLIENT_ID, UNTAPPD_CLIENT_SECRET
from ..utils import get_retrying_session
from .structs import UserInfo

AUTH_REDIRECT_URL = "https://strinks.zeletochoy.fr/auth"
UNTAPPD_OAUTH_URL = (
    "https://untappd.com/oauth/authenticate/"
    f"?client_id={UNTAPPD_CLIENT_ID}&response_type=code&redirect_url={AUTH_REDIRECT_URL}"
)
API_URL = "https://api.untappd.com/v4"
HEADERS = {"User-Agent": f"Strinks ({UNTAPPD_CLIENT_ID})"}

session = get_retrying_session()


def untappd_get_oauth_token(auth_code: str) -> str:
    res = session.get(
        "https://untappd.com/oauth/authorize/",
        headers=HEADERS,
        params={
            "client_id": UNTAPPD_CLIENT_ID,
            "client_secret": UNTAPPD_CLIENT_SECRET,
            "response_type": "code",
            "redirect_url": AUTH_REDIRECT_URL,
            "code": auth_code,
        },
    )
    res.raise_for_status()
    data = res.json()
    # The Untappd API returns {"response": {"access_token": "..."}} on success
    access_token = data["response"]["access_token"]
    if not isinstance(access_token, str):
        raise ValueError(f"Expected string access_token, got {type(access_token)}")
    return access_token


def untappd_get_user_info(access_token: str) -> UserInfo:
    res = session.get(
        API_URL + "/user/info",
        headers=HEADERS,
        params={
            "access_token": access_token,
            "compact": "true",
        },
    )
    res.raise_for_status()
    user_json = res.json()["response"]["user"]
    return UserInfo(
        user_id=user_json["id"],
        user_name=user_json["user_name"],
        first_name=user_json["first_name"],
        last_name=user_json["last_name"],
        avatar_url=user_json["user_avatar"],
        access_token=access_token,
    )


def get_untappd_api_auth_params(access_token: str | None = None) -> dict[str, str]:
    if access_token is not None:
        return {"access_token": access_token}
    return {"client_id": UNTAPPD_CLIENT_ID, "client_secret": UNTAPPD_CLIENT_SECRET}
