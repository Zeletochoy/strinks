from contextlib import contextmanager
from pathlib import Path
from typing import Type, TypeVar, Union

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
