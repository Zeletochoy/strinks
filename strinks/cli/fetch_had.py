from typing import NamedTuple, Optional

import click
from sqlalchemy.exc import IntegrityError

from strinks.api.untappd import UntappdAPI, UntappdClient
from strinks.db import BeerDB, get_db
from strinks.db.tables import User


class FetchSummary(NamedTuple):
    new_beers: int
    new_ratings: int

    def __str__(self):
        return f"Fetched {self.new_ratings} new rating(s) and added {self.new_beers} new beer(s)."


def fetch_user_had(user: User, db: BeerDB, verbose: bool) -> FetchSummary:
    untappd = UntappdClient(UntappdAPI(user.access_token))
    latest_rating = db.get_latest_rating(user.id)
    from_time = latest_rating.updated_at if latest_rating is not None else None
    new_beers = new_ratings = 0
    for beer, rating in untappd.iter_had_beers(from_time=from_time):
        if rating.rating is None:  # not rated
            continue
        # TODO: DB beers/ratings not updated
        try:
            with db.commit_or_rollback():
                db_beer = db.insert_beer(
                    beer_id=beer.beer_id,
                    image_url=beer.image_url,
                    name=beer.name,
                    brewery=beer.brewery,
                    style=beer.style,
                    abv=beer.abv,
                    ibu=beer.ibu,
                    rating=beer.rating,
                    description=beer.description,
                )
            new_beers += 1
        except IntegrityError:
            pass  # Already exists
        try:
            with db.commit_or_rollback():
                db.insert_rating(db_beer.beer_id, user.id, rating.rating, rating.updated_at)
            new_ratings += 1
        except IntegrityError:
            pass
        if verbose:
            print(f"{beer}: {rating.rating}")
    return FetchSummary(new_beers, new_ratings)


@click.command()
@click.option(
    "-d",
    "--database",
    type=click.Path(dir_okay=False, exists=True),
    default=None,
    help="Database path, default: <package_root>/db.sqlite",
)
@click.option("-u", "--user-id", type=int, default=None, help="User ID, default: all")
@click.option("-v", "--verbose", is_flag=True, help="Display debug info")
def cli(database: Optional[click.Path], user_id: Optional[int], verbose: bool):
    db = get_db(str(database) if database is not None else None)

    if user_id is None:
        users = db.get_users()
    else:
        user = db.get_user(user_id)
        if user is None:
            raise click.BadOptionUsage("-u", "user not found")
        users = [user]

    summary = {}

    try:
        for user in users:
            print(f"Fetching beers had by {user.user_name}...")
            try:
                user_summary = fetch_user_had(user, db, verbose)
                summary[user.user_name] = str(user_summary)
            except Exception:
                from traceback import format_exc

                formatted = f"Error: {format_exc()}"
                summary[user.user_name] = formatted
                print(formatted)
    finally:
        print("=" * 10, "Summary", "=" * 10)
        for user_name, summary_str in summary.items():
            print(f"- {user_name}: {summary_str}")
    print("Done.")
