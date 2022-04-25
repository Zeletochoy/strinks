from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Iterator, List, Optional, Sequence, Tuple, Type, TypeVar, Union

from sqlalchemy import create_engine, func, or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql.expression import desc
from sqlalchemy_utils import escape_like

from .tables import Beer, BeerTag, FlavorTag, Offering, Shop, User, UserRating


if TYPE_CHECKING:
    from ..api.untappd import UserInfo


T = TypeVar("T")


class BeerDB:
    def __init__(self, path: Union[str, Path, None] = None, read_only=True, debug_echo=False):
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
        self.session_maker = sessionmaker(bind=self.engine)
        self.session = self.session_maker()

        Beer.__table__.create(self.engine, checkfirst=True)
        Shop.__table__.create(self.engine, checkfirst=True)
        Offering.__table__.create(self.engine, checkfirst=True)
        User.__table__.create(self.engine, checkfirst=True)
        UserRating.__table__.create(self.engine, checkfirst=True)
        FlavorTag.__table__.create(self.engine, checkfirst=True)
        BeerTag.__table__.create(self.engine, checkfirst=True)

    def __del__(self):
        try:
            self.session.close()
        except Exception:
            pass

    def _insert(self, _check_existence: bool, table: Type[T], **params) -> T:
        if _check_existence:
            instance = self.session.query(table).filter_by(**params).first()
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
        free_shipping_over: Optional[int] = None,
        check_existence: bool = True,
    ) -> Shop:
        if check_existence:
            shop = self.session.query(Shop).filter_by(name=name).first()
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
        brewery: str,
        style: str,
        abv: float,
        ibu: float,
        rating: float,
        description: Optional[str] = None,
        tags: Optional[Sequence[Tuple[FlavorTag, int]]] = None,
        check_existence: bool = True,
    ) -> Beer:
        beer = None
        if check_existence:
            beer = self.session.query(Beer).filter_by(beer_id=beer_id).first()
            if beer is not None:
                beer.image_url = image_url
                beer.name = name
                beer.brewery = brewery
                beer.style = style
                beer.abv = Decimal(abv)
                beer.ibu = Decimal(ibu)
                beer.rating = Decimal(rating)
                beer.updated_at = datetime.now()
                beer.description = description
        if beer is None:
            beer = Beer(
                beer_id=beer_id,
                image_url=image_url,
                name=name,
                brewery=brewery,
                style=style,
                abv=Decimal(abv),
                ibu=Decimal(ibu),
                rating=Decimal(rating),
                updated_at=datetime.now(),
                description=description,
            )
            self.session.add(beer)
        if tags is not None:
            for flavor_tag, count in tags:
                beer.tags.append(BeerTag(beer_id=beer_id, tag_id=flavor_tag.tag_id, count=count))
        return beer

    def get_beer(self, beer_id: int) -> Optional[Beer]:
        return self.session.query(Beer).filter_by(beer_id=beer_id).one_or_none()

    def insert_offering(
        self,
        shop: Shop,
        beer: Beer,
        url: str,
        milliliters: int,
        price: int,
        image_url: Optional[str] = None,
        check_existence: bool = True,
    ) -> Offering:
        if check_existence:
            offering = self.session.query(Offering).filter_by(shop_id=shop.shop_id, beer_id=beer.beer_id).first()
            if offering is not None:
                offering.url = url
                offering.milliliters = milliliters
                offering.price = price
                offering.image_url = image_url
                offering.updated_at = datetime.now()
                return offering
        offering = Offering(
            shop_id=shop.shop_id,
            beer_id=beer.beer_id,
            url=url,
            milliliters=milliliters,
            price=price,
            image_url=image_url,
            updated_at=datetime.now(),
        )
        self.session.add(offering)
        return offering

    def get_best_cospa(
        self,
        n: int,
        value_factor: float = 8,
        search: Optional[str] = None,
        shop_id: Optional[int] = None,
        styles: Optional[Iterable[str]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        exclude_user_had: Optional[int] = None,  # user ID
    ) -> Iterator[Beer]:
        def beer_value(rating, cost):
            return (value_factor**rating) / cost

        conn = self.engine.raw_connection()
        conn.create_function("beer_value", 2, beer_value)

        query = self.session.query(Beer).filter(Beer.rating != 0).join(Offering).filter(Offering.price != 0)

        if search is not None:
            like = f"%{escape_like(search)}%"
            query = query.filter(
                or_(
                    Beer.name.ilike(like),
                    Beer.brewery.ilike(like),
                )
            )

        if min_price is not None:
            query = query.filter(Offering.price >= min_price)
        if max_price is not None:
            query = query.filter(Offering.price <= max_price)

        if shop_id is not None:
            query = query.filter_by(shop_id=shop_id)

        if styles is not None:
            query = query.filter(Beer.style.in_(styles))

        if exclude_user_had is not None:
            query = query.filter(~Beer.ratings.any(UserRating.user_id == exclude_user_had))

        return query.order_by(func.beer_value(Beer.rating, Offering.price_per_ml).desc()).distinct().limit(n).all()

    def get_shops(self) -> Iterator[Shop]:
        return self.session.query(Shop).order_by(Shop.name).all()

    def remove_expired_offerings(self, shop: Shop, valid_ids: Iterable[int]) -> None:
        (
            self.session.query(Offering)
            .filter_by(shop_id=shop.shop_id)
            .filter(~Offering.beer_id.in_(valid_ids))
            .delete(synchronize_session=False)
        )

    def create_user(self, user_info: "UserInfo") -> User:
        user = User(
            id=user_info.id,
            user_name=user_info.user_name,
            first_name=user_info.first_name,
            last_name=user_info.last_name,
            avatar_url=user_info.avatar_url,
            access_token=user_info.access_token,
        )
        self.session.add(user)
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        return self.session.query(User).filter_by(id=user_id).one_or_none()

    def get_users(self) -> List[User]:
        return self.session.query(User).all()

    def get_latest_rating(self, user_id: int) -> Optional[UserRating]:
        return (
            self.session.query(UserRating)
            .filter_by(user_id=user_id)
            .order_by(desc(UserRating.updated_at))
            .limit(1)
            .one_or_none()
        )

    def insert_rating(
        self,
        beer_id: int,
        user_id: int,
        rating: float,
        updated_at: datetime,
        check_existence: bool = True,
    ) -> UserRating:
        if check_existence:
            user_rating = self.session.query(UserRating).filter_by(beer_id=beer_id, user_id=user_id).first()
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

    def get_access_tokens(self, is_app: Optional[bool] = None) -> List[str]:
        query = self.session.query(User.access_token)
        if is_app is not None:
            query = query.filter_by(is_app=is_app)
        return [token for token, in query.all()]
