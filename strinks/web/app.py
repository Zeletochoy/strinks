from flask import Flask, render_template, request

from ..api.styles import STYLES, get_styles_by_ids
from ..db import get_db


app = Flask(__name__)


TOP_N = 150


@app.route("/")
@app.route("/beers")
def offerings():
    db = get_db()
    shop_id = request.args.get("shop_id", default=None, type=int)
    value_factor = request.args.get("value_factor", default=8, type=float)

    style_ids_str = request.args.get("styles", default="", type=str)
    style_ids = [int(i) for i in style_ids_str.split(",")] if style_ids_str else None
    enabled_styles = get_styles_by_ids(style_ids) if style_ids else None

    beers = db.get_best_cospa(TOP_N, value_factor, shop_id=shop_id, styles=enabled_styles).all()
    shops = db.get_shops()

    return render_template(
        "offerings.html",
        beers=beers,
        shops=shops,
        shop_id=shop_id,
        value_factor=value_factor,
        styles=STYLES,
        enabled_styles=set(style_ids) if style_ids else None,
    )


@app.route("/shops")
def shops():
    db = get_db()
    shops = db.get_shops().all()
    return render_template("shops.html", shops=shops)
