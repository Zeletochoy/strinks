from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, cast
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship


Base = declarative_base()


class Beer(Base):
    __tablename__ = "beers"

    beer_id = Column(Integer, primary_key=True)
    image_url = Column(String, nullable=False)
    name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    brewery = Column(String, nullable=False)
    style = Column(String, nullable=False)
    abv = Column(Float, nullable=False)
    ibu = Column(Float, nullable=False)
    rating = Column(Float, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    offerings = relationship("Offering", back_populates="beer")

    def __str__(self) -> str:
        return f"{self.brewery} - {self.name} ({self.style}, {self.abv}%, {self.ibu}IBU, {self.rating:0.02f})"

    def __repr__(self) -> str:
        return f"Beer({str(self)})"


class Shop(Base):
    __tablename__ = "shops"

    shop_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    shipping_fee = Column(Integer, nullable=False)
    free_shipping_over = Column(Integer, nullable=False)

    offerings = relationship("Offering", back_populates="shop")


class Offering(Base):
    __tablename__ = "offerings"

    shop_beer_id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey(f"{Shop.__tablename__}.shop_id"), nullable=False, index=True)
    beer_id = Column(Integer, ForeignKey(f"{Beer.__tablename__}.beer_id"), nullable=False, index=True)
    milliliters = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    image_url = Column(String)
    updated_at = Column(DateTime, nullable=False)

    beer = relationship("Beer", back_populates="offerings")
    shop = relationship("Shop", back_populates="offerings")

    @hybrid_property
    def price_per_ml(self) -> float:
        return self.price / self.milliliters

    @price_per_ml.expression
    def price_per_ml(self):
        return cast(self.price, Float) / cast(self.milliliters, Float)
