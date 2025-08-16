from datetime import datetime
from typing import ClassVar

from sqlalchemy import Column, DateTime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlmodel import Field, Relationship, SQLModel

# Constants
APP_USER_MARKER = "APP"  # Users with last_name == "APP" are app tokens, not real users


class Beer(SQLModel, table=True):
    __tablename__ = "beers"

    beer_id: int = Field(primary_key=True)
    image_url: str
    name: str
    brewery: str
    style: str
    abv: float
    ibu: float | None = None
    rating: float
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    description: str | None = None

    offerings: list["Offering"] = Relationship(back_populates="beer")
    ratings: list["UserRating"] = Relationship(back_populates="beer")
    tags: list["BeerTag"] = Relationship(back_populates="beer")

    @property
    def tag_names(self) -> set[str]:
        return {assoc.tag.name for assoc in self.tags}

    def __str__(self) -> str:
        return f"{self.brewery} - {self.name} ({self.style}, {self.abv}%, {self.ibu}IBU, {self.rating:0.02f})"

    def __repr__(self) -> str:
        return f"Beer({self!s})"


class Brewery(SQLModel, table=True):
    __tablename__ = "breweries"

    brewery_id: int = Field(primary_key=True)
    image_url: str
    name: str
    country: str

    def __str__(self) -> str:
        return f"{self.name} ({self.country})"

    def __repr__(self) -> str:
        return f"Brewery({self!s})"


class BeerTag(SQLModel, table=True):
    __tablename__ = "beer_tags"

    beer_id: int = Field(foreign_key="beers.beer_id", primary_key=True, index=True)
    beer: Beer = Relationship(back_populates="tags")

    tag_id: int = Field(foreign_key="flavor_tags.tag_id", primary_key=True, index=True)
    tag: "FlavorTag" = Relationship(back_populates="beers")

    count: int


class FlavorTag(SQLModel, table=True):
    __tablename__ = "flavor_tags"

    tag_id: int = Field(primary_key=True)
    name: str

    beers: list[BeerTag] = Relationship(back_populates="tag")

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"FlavorTag({self!s})"


class Shop(SQLModel, table=True):
    __tablename__ = "shops"

    shop_id: int = Field(primary_key=True)
    name: str
    url: str
    image_url: str
    shipping_fee: int
    free_shipping_over: int | None = None

    offerings: list["Offering"] = Relationship(back_populates="shop")

    def __str__(self) -> str:
        return f"{self.name} ({self.url}, {self.shipping_fee})"

    def __repr__(self) -> str:
        return f"Shop({self!s})"


class Offering(SQLModel, table=True):
    __tablename__ = "offerings"

    shop_id: int = Field(foreign_key="shops.shop_id", primary_key=True, index=True)
    shop: Shop = Relationship(back_populates="offerings")

    beer_id: int = Field(foreign_key="beers.beer_id", primary_key=True, index=True)
    beer: Beer = Relationship(back_populates="offerings")

    url: str
    milliliters: int
    price: int
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, primary_key=True))
    image_url: str | None = None

    @property
    def price_per_ml(self) -> float:
        return self.price / self.milliliters

    def __str__(self) -> str:
        return f"{self.shop} {self.beer}: {self.price}¥/{self.milliliters}ml"

    def __repr__(self) -> str:
        return f"Offering({self!s})"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int = Field(primary_key=True)
    user_name: str
    first_name: str
    last_name: str
    avatar_url: str
    access_token: str

    ratings: list["UserRating"] = Relationship(back_populates="user")

    @hybrid_property
    def is_app(self) -> bool:
        return self.last_name == APP_USER_MARKER

    # Type annotation to tell Pydantic to ignore this
    is_app: ClassVar[hybrid_property] = is_app  # type: ignore[no-redef]

    def __str__(self) -> str:
        return self.user_name

    def __repr__(self) -> str:
        return f"User({self!s})"


class UserRating(SQLModel, table=True):
    __tablename__ = "user_ratings"

    user_id: int = Field(foreign_key="users.id", primary_key=True, index=True)
    user: User = Relationship(back_populates="ratings")

    beer_id: int = Field(foreign_key="beers.beer_id", primary_key=True, index=True)
    beer: Beer = Relationship(back_populates="ratings")

    rating: float
    updated_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class UntappdCache(SQLModel, table=True):
    """Cache for Untappd beer search results."""

    __tablename__ = "untappd_cache"

    id: int | None = Field(default=None, primary_key=True)
    query: str = Field(unique=True, index=True)  # The search query
    beer_id: int | None = Field(default=None, foreign_key="beers.beer_id")  # None for not found
    beer: Beer | None = Relationship()
    created_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))


class DeepLCache(SQLModel, table=True):
    """Cache for DeepL translations."""

    __tablename__ = "deepl_cache"

    source_text: str = Field(primary_key=True)  # Japanese text to translate
    translated_text: str  # English translation
