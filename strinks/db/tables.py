from typing import List

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, cast
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship


_Base = declarative_base()


class Beer(_Base):
    __tablename__ = "beers"

    beer_id = Column(Integer, primary_key=True)
    image_url = Column(String, nullable=False)
    name = Column(String, nullable=False)
    brewery = Column(String, nullable=False)
    style = Column(String, nullable=False)
    abv = Column(Float, nullable=False)
    ibu = Column(Float)
    rating = Column(Float, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    description = Column(String, nullable=True)

    offerings = relationship("Offering", back_populates="beer")
    ratings = relationship("UserRating", back_populates="beer")
    tags = relationship("BeerTag", back_populates="beer")

    @property
    def tag_names(self) -> List[str]:
        return [assoc.tag.name for assoc in self.tags]

    def __str__(self) -> str:
        return f"{self.brewery} - {self.name} ({self.style}, {self.abv}%, {self.ibu}IBU, {self.rating:0.02f})"

    def __repr__(self) -> str:
        return f"Beer({str(self)})"


class BeerTag(_Base):
    __tablename__ = "beer_tags"

    beer_id = Column(Integer, ForeignKey("beers.beer_id"), primary_key=True, index=True)
    beer = relationship(Beer, back_populates="tags")

    tag_id = Column(Integer, ForeignKey("flavor_tags.tag_id"), primary_key=True, index=True)
    tag = relationship("FlavorTag", back_populates="beers")

    count = Column(Integer, nullable=False)


class FlavorTag(_Base):
    __tablename__ = "flavor_tags"

    tag_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    beers = relationship(BeerTag, back_populates="tag")


class Shop(_Base):
    __tablename__ = "shops"

    shop_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    image_url = Column(String, nullable=False)
    shipping_fee = Column(Integer, nullable=False)
    free_shipping_over = Column(Integer)

    offerings = relationship("Offering", back_populates="shop")


class Offering(_Base):
    __tablename__ = "offerings"

    shop_id = Column(Integer, ForeignKey(f"{Shop.__tablename__}.shop_id"), primary_key=True, index=True)
    beer_id = Column(Integer, ForeignKey(f"{Beer.__tablename__}.beer_id"), primary_key=True, index=True)
    url = Column(String, nullable=False)
    milliliters = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    image_url = Column(String)
    updated_at = Column(DateTime, nullable=False)

    beer = relationship("Beer", back_populates="offerings")
    shop = relationship("Shop", back_populates="offerings")

    @hybrid_property
    def price_per_ml(self) -> float:
        return self.price / self.milliliters

    @price_per_ml.expression  # type: ignore[no-redef]
    def price_per_ml(self):
        return cast(self.price, Float) / cast(self.milliliters, Float)


class User(_Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_name = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=False)
    access_token = Column(String, nullable=False)

    ratings = relationship("UserRating", back_populates="user")

    @hybrid_property
    def is_app(self) -> bool:
        return self.last_name == "APP"


class UserRating(_Base):
    __tablename__ = "user_ratings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    user = relationship(User, back_populates="ratings")

    beer_id = Column(Integer, ForeignKey("beers.beer_id"), primary_key=True, index=True)
    beer = relationship(Beer, back_populates="ratings")

    rating = Column(Float, nullable=False)
    updated_at = Column(DateTime, nullable=False)
