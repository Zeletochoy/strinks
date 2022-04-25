from datetime import datetime
from typing import List, Set

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, cast
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship


_Base = declarative_base()


class Beer(_Base):
    __tablename__ = "beers"

    beer_id: int = Column(Integer, primary_key=True)
    image_url: str = Column(String, nullable=False)
    name: str = Column(String, nullable=False)
    brewery: str = Column(String, nullable=False)
    style: str = Column(String, nullable=False)
    abv: float = Column(Float, nullable=False)
    ibu = Column(Float)
    rating: float = Column(Float, nullable=False)
    updated_at: datetime = Column(DateTime, nullable=False)
    description = Column(String, nullable=True)

    offerings: List["Offering"] = relationship("Offering", back_populates="beer")
    ratings: List["UserRating"] = relationship("UserRating", back_populates="beer")
    tags: List["BeerTag"] = relationship("BeerTag", back_populates="beer")

    @property
    def tag_names(self) -> Set[str]:
        return {assoc.tag.name for assoc in self.tags}

    def __str__(self) -> str:
        return f"{self.brewery} - {self.name} ({self.style}, {self.abv}%, {self.ibu}IBU, {self.rating:0.02f})"

    def __repr__(self) -> str:
        return f"Beer({str(self)})"


class BeerTag(_Base):
    __tablename__ = "beer_tags"

    beer_id: int = Column(Integer, ForeignKey("beers.beer_id"), primary_key=True, index=True)
    beer: Beer = relationship(Beer, back_populates="tags", uselist=False)

    tag_id: int = Column(Integer, ForeignKey("flavor_tags.tag_id"), primary_key=True, index=True)
    tag: "FlavorTag" = relationship("FlavorTag", back_populates="beers", uselist=False)

    count: int = Column(Integer, nullable=False)


class FlavorTag(_Base):
    __tablename__ = "flavor_tags"

    tag_id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)

    beers: List["BeerTag"] = relationship("BeerTag", back_populates="tag")


class Shop(_Base):
    __tablename__ = "shops"

    shop_id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)
    url: str = Column(String, nullable=False)
    image_url: str = Column(String, nullable=False)
    shipping_fee: int = Column(Integer, nullable=False)
    free_shipping_over = Column(Integer)

    offerings: List["Offering"] = relationship("Offering", back_populates="shop")


class Offering(_Base):
    __tablename__ = "offerings"

    shop_id: int = Column(Integer, ForeignKey(f"{Shop.__tablename__}.shop_id"), primary_key=True, index=True)
    beer_id: int = Column(Integer, ForeignKey(f"{Beer.__tablename__}.beer_id"), primary_key=True, index=True)
    url: str = Column(String, nullable=False)
    milliliters: int = Column(Integer, nullable=False)
    price: int = Column(Integer, nullable=False)
    image_url = Column(String)
    updated_at: datetime = Column(DateTime, nullable=False)

    beer: Beer = relationship(Beer, back_populates="offerings", uselist=False)
    shop: Shop = relationship(Shop, back_populates="offerings", uselist=False)

    @hybrid_property
    def price_per_ml(self) -> float:
        return self.price / self.milliliters

    @price_per_ml.expression  # type: ignore[no-redef]
    def price_per_ml(self):
        return cast(self.price, Float) / cast(self.milliliters, Float)


class User(_Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True)
    user_name: str = Column(String, nullable=False)
    first_name: str = Column(String, nullable=False)
    last_name: str = Column(String, nullable=False)
    avatar_url: str = Column(String, nullable=False)
    access_token: str = Column(String, nullable=False)

    ratings: List["UserRating"] = relationship("UserRating", back_populates="user")

    @hybrid_property
    def is_app(self) -> bool:
        return self.last_name == "APP"


class UserRating(_Base):
    __tablename__ = "user_ratings"

    user_id: int = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    user: User = relationship(User, back_populates="ratings", uselist=False)

    beer_id: int = Column(Integer, ForeignKey("beers.beer_id"), primary_key=True, index=True)
    beer: Beer = relationship(Beer, back_populates="ratings", uselist=False)

    rating: float = Column(Float, nullable=False)
    updated_at: datetime = Column(DateTime, nullable=False)
