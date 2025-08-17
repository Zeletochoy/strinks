from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

from sqlalchemy import func, or_
from sqlalchemy.pool import StaticPool
from sqlalchemy_utils import escape_like
from sqlmodel import Session, SQLModel, col, create_engine, delete, select

from ..api.utils import now_jst
from .tables import Beer, BeerTag, Brewery, FlavorTag, Offering, Shop, User, UserRating

if TYPE_CHECKING:
    from ..api.untappd import UserInfo


T = TypeVar("T")


class BeerDB:
    def __init__(self, path: str | Path | None = None, read_only=True, debug_echo=False):
        """
        path: path to the sqlite database file or None for in-memory
        debug_echo: log SQL queries
        """
        self.debug_echo = debug_echo
        if path is None:
            db_uri = ":memory:"
        else:
            db_uri = f"/file:{Path(path).resolve()}?uri=true"
            if read_only:
                db_uri += "&mode=ro"
        self.engine = create_engine(f"sqlite://{db_uri}", echo=debug_echo, poolclass=StaticPool)
        self.session = Session(self.engine)

        SQLModel.metadata.create_all(self.engine, checkfirst=True)

    def __del__(self):
        with suppress(Exception):
            self.session.close()

    def _insert(self, _check_existence: bool, table: type[T], **params) -> T:
        if _check_existence:
            statement = select(table).filter_by(**params)
            instance = self.session.exec(statement).first()
        else:
            instance = None
        if not instance:
            instance = table(**params)  # type: ignore
            self.session.add(instance)
        return instance

    @contextmanager
    def commit_or_rollback(self):
        try:
            yield
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def insert_shop(
        self,
        name: str,
        url: str,
        image_url: str,
        shipping_fee: int,
        free_shipping_over: int | None = None,
        check_existence: bool = True,
    ) -> Shop:
        if check_existence:
            statement = select(Shop).where(Shop.name == name)
            shop = self.session.exec(statement).first()
            if shop is not None:
                shop.url = url
                shop.image_url = image_url
                shop.shipping_fee = shipping_fee
                shop.free_shipping_over = free_shipping_over
                return shop
        shop = Shop(
            name=name,
            url=url,
            image_url=image_url,
            shipping_fee=shipping_fee,
            free_shipping_over=free_shipping_over,
        )
        self.session.add(shop)
        return shop

    def insert_beer(
        self,
        beer_id: int,
        image_url: str,
        name: str,
        brewery_id: int,
        style: str,
        abv: float,
        ibu: float,
        rating: float,
        description: str | None = None,
        tags: Sequence[tuple[FlavorTag, int]] | None = None,
        weighted_rating: float | None = None,
        rating_count: int | None = None,
        total_user_count: int | None = None,
        check_existence: bool = True,
    ) -> Beer:
        beer = None
        if check_existence:
            statement = select(Beer).where(Beer.beer_id == beer_id)
            beer = self.session.exec(statement).first()
            if beer is not None:
                beer.image_url = image_url
                beer.name = name
                beer.brewery_id = brewery_id
                beer.style = style
                beer.abv = abv
                beer.ibu = ibu
                beer.rating = rating
                beer.weighted_rating = weighted_rating
                beer.rating_count = rating_count
                beer.total_user_count = total_user_count
                beer.updated_at = now_jst()
                beer.description = description
        if beer is None:
            beer = Beer(
                beer_id=beer_id,
                image_url=image_url,
                name=name,
                brewery_id=brewery_id,
                style=style,
                abv=abv,
                ibu=ibu,
                rating=rating,
                weighted_rating=weighted_rating,
                rating_count=rating_count,
                total_user_count=total_user_count,
                updated_at=now_jst(),
                description=description,
            )
            self.session.add(beer)
        if tags is not None:
            for flavor_tag, count in tags:
                beer.tags.append(BeerTag(beer_id=beer_id, tag_id=flavor_tag.tag_id, count=count))

        return beer

    def get_beer(self, beer_id: int) -> Beer | None:
        statement = select(Beer).where(Beer.beer_id == beer_id)
        return self.session.exec(statement).one_or_none()

    def insert_offering(
        self,
        shop: Shop,
        beer: Beer,
        url: str,
        milliliters: int,
        price: int,
        image_url: str | None = None,
        check_existence: bool = True,
    ) -> Offering:
        if check_existence:
            statement = select(Offering).where(Offering.shop_id == shop.shop_id, Offering.beer_id == beer.beer_id)
            offering = self.session.exec(statement).first()
            if offering is not None:
                offering.url = url
                offering.milliliters = milliliters
                offering.price = price
                offering.image_url = image_url
                offering.updated_at = now_jst()
                # Keep created_at unchanged for existing offerings
                return offering
        now = now_jst()
        offering = Offering(
            shop_id=shop.shop_id,
            beer_id=beer.beer_id,
            url=url,
            milliliters=milliliters,
            price=price,
            image_url=image_url,
            created_at=now,  # Set created_at only for new offerings
            updated_at=now,
        )
        self.session.add(offering)
        return offering

    def get_best_cospa(
        self,
        n: int,
        value_factor: float = 8,
        search: str | None = None,
        shop_id: int | None = None,
        styles: Iterable[str] | None = None,
        min_price: int | None = None,
        max_price: int | None = None,
        exclude_user_had: int | None = None,  # user ID
        countries: Iterable[str] | None = None,
        offset: int = 0,
    ) -> Iterator[Beer]:
        def beer_value(rating, cost):
            return (value_factor**rating) / cost

        conn = self.engine.raw_connection()
        conn.create_function("beer_value", 2, beer_value)  # type: ignore

        statement = select(Beer).join(Offering).join(Brewery).where(Beer.rating != 0, Offering.price != 0)

        if search is not None:
            like = f"%{escape_like(search)}%"
            statement = statement.where(
                or_(
                    col(Beer.name).ilike(like),
                    col(Brewery.name).ilike(like),
                )
            )

        if min_price is not None:
            statement = statement.where(Offering.price >= min_price)
        if max_price is not None:
            statement = statement.where(Offering.price <= max_price)

        if shop_id is not None:
            statement = statement.where(Offering.shop_id == shop_id)

        if styles is not None:
            statement = statement.where(col(Beer.style).in_(styles))

        if countries is not None:
            statement = statement.where(col(Brewery.country).in_(countries))

        if exclude_user_had is not None:
            # For relationship.any(), we need to use exists subquery
            from sqlalchemy import exists

            subquery = select(UserRating).where(
                UserRating.beer_id == Beer.beer_id, UserRating.user_id == exclude_user_had
            )
            statement = statement.where(~exists(subquery))

        # Sort by created_at for "First Dibs" profile (value_factor=0), otherwise by value
        if value_factor == 0:
            statement = statement.order_by(col(Offering.created_at).desc()).distinct().limit(n).offset(offset)
        else:
            statement = (
                statement.order_by(func.beer_value(Beer.rating, Offering.price / Offering.milliliters).desc())
                .distinct()
                .limit(n)
                .offset(offset)
            )

        return self.session.exec(statement)

    def get_shops(self) -> Iterator[Shop]:
        statement = select(Shop).order_by(Shop.name)
        return self.session.exec(statement)

    def get_countries(self) -> list[tuple[str, int]]:
        """Get all countries with unique beer count, sorted by count."""
        beer_count = func.count(col(Beer.beer_id).distinct())
        statement = (
            select(Brewery.country, beer_count.label("count"))
            .select_from(Beer)
            .join(Brewery)
            .join(Offering)  # Only countries with current offerings
            .group_by(Brewery.country)
            .order_by(beer_count.desc())
        )
        return list(self.session.exec(statement))

    def remove_expired_offerings(self, shop: Shop, valid_ids: Iterable[int]) -> None:
        statement = delete(Offering).where(col(Offering.shop_id) == shop.shop_id, ~col(Offering.beer_id).in_(valid_ids))
        self.session.execute(statement)

    def create_user(self, user_info: "UserInfo") -> User:
        user = User(
            id=user_info.user_id,
            user_name=user_info.user_name,
            first_name=user_info.first_name,
            last_name=user_info.last_name,
            avatar_url=user_info.avatar_url,
            access_token=user_info.access_token,
        )
        self.session.add(user)
        return user

    def get_user(self, user_id: int) -> User | None:
        statement = select(User).where(User.id == user_id)
        return self.session.exec(statement).one_or_none()

    def get_users(self) -> list[User]:
        statement = select(User)
        return list(self.session.exec(statement))

    def drop_users(self) -> None:
        SQLModel.metadata.tables[User.__tablename__].drop(self.engine)

    def get_latest_rating(self, user_id: int) -> UserRating | None:
        statement = (
            select(UserRating).where(UserRating.user_id == user_id).order_by(col(UserRating.updated_at).desc()).limit(1)
        )
        return self.session.exec(statement).one_or_none()

    def insert_rating(
        self,
        beer_id: int,
        user_id: int,
        rating: float,
        updated_at: datetime,
        check_existence: bool = True,
    ) -> UserRating:
        if check_existence:
            statement = select(UserRating).where(UserRating.beer_id == beer_id, UserRating.user_id == user_id)
            user_rating = self.session.exec(statement).first()
            if user_rating is not None:
                user_rating.rating = rating
                user_rating.updated_at = updated_at
                return user_rating
        user_rating = UserRating(
            beer_id=beer_id,
            user_id=user_id,
            rating=rating,
            updated_at=updated_at,
        )
        self.session.add(user_rating)
        return user_rating

    def insert_brewery(
        self,
        brewery_id: int,
        image_url: str,
        name: str,
        country: str,
        city: str | None = None,
        state: str | None = None,
        check_existence: bool = True,
    ) -> Brewery:
        if check_existence:
            statement = select(Brewery).where(Brewery.brewery_id == brewery_id)
            brewery = self.session.exec(statement).first()
            if brewery is not None:
                brewery.image_url = image_url
                brewery.name = name
                brewery.country = country
                brewery.city = city
                brewery.state = state
                return brewery
        brewery = Brewery(
            brewery_id=brewery_id,
            image_url=image_url,
            name=name,
            country=country,
            city=city,
            state=state,
        )
        self.session.add(brewery)
        return brewery

    def get_access_tokens(self, is_app: bool | None = None) -> list[str]:
        statement = select(User.access_token)

        if is_app is not None:
            statement = statement.where(User.is_app == is_app)

        results = self.session.exec(statement)
        return [token for token in results if token is not None]
