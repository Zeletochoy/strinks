from flask import Flask, render_template

from ..db import get_db


app = Flask(__name__)


@app.route("/")
@app.route("/beers")
def offerings():
    db = get_db()
    beers = db.get_best_cospa(12).all()
    return render_template("offerings.html", beers=beers)
