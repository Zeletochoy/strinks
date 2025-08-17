from flask import Flask, make_response, redirect, render_template, request

from ..api.styles import GROUPED_STYLES_WITH_IDS, STYLES, get_styles_by_ids
from ..api.untappd import UNTAPPD_OAUTH_URL, untappd_get_oauth_token, untappd_get_user_info
from ..db import get_db

app = Flask(__name__)


TOP_N = 150
USER_ID_COOKIE = "strinks_user_id"


@app.route("/")
@app.route("/beers")
def offerings():
    db = get_db()
    shop_id = request.args.get("shop_id", default=None, type=int)
    value_factor = request.args.get("value_factor", default=8.0, type=float) or 8.0
    search = request.args.get("search", default=None, type=str)
    min_price = request.args.get("min_price", default=None, type=int)
    max_price = request.args.get("max_price", default=None, type=int)
    exclude_had = request.args.get("exclude_had", default="", type=str) == "on"

    style_ids_str = request.args.get("styles", default="", type=str)
    style_ids = [int(i) for i in style_ids_str.split(",")] if style_ids_str else None
    enabled_styles = get_styles_by_ids(style_ids) if style_ids else None

    countries_str = request.args.get("countries", default="", type=str)
    selected_countries = countries_str.split(",") if countries_str else None

    user_id = request.cookies.get(USER_ID_COOKIE, None)
    user = db.get_user(int(user_id)) if user_id is not None else None
    user_ratings = {rating.beer.beer_id: rating.rating for rating in (user.ratings if user is not None else [])}

    beers = db.get_best_cospa(
        TOP_N,
        value_factor,
        search=search,
        min_price=min_price,
        max_price=max_price,
        shop_id=shop_id,
        styles=enabled_styles,
        exclude_user_had=user.id if exclude_had and user is not None else None,
        countries=selected_countries,
    )
    shops = db.get_shops()
    countries = db.get_countries()

    return render_template(
        "offerings.html",
        beers=beers,
        shops=shops,
        shop_id=shop_id,
        value_factor=value_factor,
        search=search,
        min_price=min_price,
        max_price=max_price,
        grouped_styles=GROUPED_STYLES_WITH_IDS,
        enabled_styles=list(set(style_ids) if style_ids else range(len(STYLES))),
        countries=countries,
        selected_countries=selected_countries or [],
        user=user,
        user_ratings=user_ratings,
        exclude_had=exclude_had,
    )


@app.route("/shops")
def shops():
    db = get_db()
    shops = db.get_shops()
    user_id = request.cookies.get(USER_ID_COOKIE, None)
    user = db.get_user(int(user_id)) if user_id is not None else None

    return render_template("shops.html", shops=shops, user=user)


@app.route("/login")
def login():
    return redirect(UNTAPPD_OAUTH_URL)


@app.route("/auth")
def auth():
    try:
        code = request.args["code"]
    except KeyError:
        return "Missing authorization code", 400

    try:
        access_token = untappd_get_oauth_token(code)
        user_info = untappd_get_user_info(access_token)
    except ValueError as e:
        # Log the error for debugging
        app.logger.error(f"OAuth error: {e}")
        return f"Authentication failed: {e}", 400
    except Exception as e:
        app.logger.error(f"Unexpected error during OAuth: {e}")
        return "Authentication failed due to an unexpected error", 500

    resp = make_response(redirect("/"))
    db = get_db()
    user = db.get_user(user_info.user_id)
    if user is None:
        with db.commit_or_rollback():
            user = db.create_user(user_info)
    resp.set_cookie(USER_ID_COOKIE, str(user.id))
    return resp
