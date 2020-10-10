from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Type, TypeVar, Union

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .tables import Beer, Offering, Shop


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
        shipping_fee: int,
        free_shipping_over: Optional[int] = None,
        check_existence: bool = True,
    ) -> Shop:
        if check_existence:
            shop = self.session.query(Shop).filter_by(name=name).first()
            if shop is not None:
                return shop
        shop = Shop(
            name=name,
            url=url,
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
        check_existence: bool = True,
    ) -> Beer:
        if check_existence:
            beer = self.session.query(Beer).filter_by(beer_id=beer_id).first()
            if beer is not None:
                return beer
        beer = Beer(
            beer_id=beer_id,
            image_url=image_url,
            name=name,
            brewery=brewery,
            style=style,
            abv=abv,
            ibu=ibu,
            rating=rating,
            updated_at=datetime.now(),
        )
        self.session.add(beer)
        return beer

    def insert_offering(
        self,
        shop: Shop,
        beer: Beer,
        milliliters: int,
        price: int,
        image_url: Optional[str] = None,
        check_existence: bool = True,
    ) -> Offering:
        if check_existence:
            offering = self.session.query(Offering).filter_by(shop_id=shop.shop_id, beer_id=beer.beer_id).first()
            if offering is not None:
                return offering
        offering = Offering(
            shop_id=shop.shop_id,
            beer_id=beer.beer_id,
            milliliters=milliliters,
            price=price,
            image_url=image_url,
            updated_at=datetime.now(),
        )
        self.session.add(offering)
        return offering
