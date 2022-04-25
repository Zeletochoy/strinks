from os import PathLike
from pathlib import Path
from typing import Union

from .. import PACKAGE_ROOT
from .models import BeerDB
from .tables import Beer, Offering, Shop


DEFAULT_DB_PATH = PACKAGE_ROOT / "db.sqlite"


def get_db(path: Union[str, "PathLike[str]", None] = None, read_only: bool = False) -> BeerDB:
    return BeerDB(Path(path) if path is not None else DEFAULT_DB_PATH, read_only=read_only)


__all__ = ("BeerDB", "Beer", "Offering", "Shop", "get_db")
