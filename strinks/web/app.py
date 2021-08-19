from flask import Flask, render_template, request, make_response, redirect

from ..api.styles import STYLES, get_styles_by_ids
from ..api.untappd import untappd_get_oauth_token, untappd_get_user_info, UNTAPPD_OAUTH_URL
from ..db import get_db


app = Flask(__name__)


TOP_N = 150
USER_ID_COOKIE = "strinks_user_id"


@app.route("/")
@app.route("/beers")
def offerings():
    db = get_db()
    shop_id = request.args.get("shop_id", default=None, type=int)
    value_factor = request.args.get("value_factor", default=8, type=float)

    style_ids_str = request.args.get("styles", default="", type=str)
    style_ids = [int(i) for i in style_ids_str.split(",")] if style_ids_str else None
    enabled_styles = get_styles_by_ids(style_ids) if style_ids else None

    beers = db.get_best_cospa(TOP_N, value_factor, shop_id=shop_id, styles=enabled_styles)
    shops = db.get_shops()
    user_id = request.cookies.get(USER_ID_COOKIE, None)
    user = db.get_user(int(user_id)) if user_id is not None else None

    return render_template(
        "offerings.html",
        beers=beers,
        shops=shops,
        shop_id=shop_id,
        value_factor=value_factor,
        styles=STYLES,
        enabled_styles=set(style_ids) if style_ids else None,
        user=user,
    )


@app.route("/shops")
def shops():
    db = get_db()
    shops = db.get_shops()
    return render_template("shops.html", shops=shops)


@app.route("/login")
def login():
    return redirect(UNTAPPD_OAUTH_URL)


@app.route("/auth")
def auth():
    try:
        code = request.args["code"]
    except KeyError:
        return "Missing code", 400
    access_token = untappd_get_oauth_token(code)
    user_info = untappd_get_user_info(access_token)
    resp = make_response(redirect("/"))
    db = get_db()
    user = db.get_user(user_info.id)
    if user is None:
        with db.commit_or_rollback():
            user = db.create_user(user_info)
    resp.set_cookie(USER_ID_COOKIE, str(user.id))
    return resp
