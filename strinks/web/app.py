from flask import Flask, render_template, request

from ..db import get_db


app = Flask(__name__)


TOP_N = 100


@app.route("/")
@app.route("/beers")
def offerings():
    db = get_db()
    shop_id = request.args.get("shop_id", default=None, type=int)
    value_factor = request.args.get("value_factor", default=8, type=float)
    beers = db.get_best_cospa(TOP_N, value_factor, shop_id=shop_id).all()
    shops = db.get_shops()
    return render_template(
        "offerings.html",
        beers=beers,
        shops=shops,
        shop_id=shop_id,
        value_factor=value_factor,
    )


@app.route("/shops")
def shops():
    db = get_db()
    shops = db.get_shops().all()
    return render_template("shops.html", shops=shops)
