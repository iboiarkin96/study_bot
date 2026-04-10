"""Declarative model base for SQLAlchemy ORM."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative registry base for all application tables.

    Subclasses declare ``__tablename__`` and :class:`~sqlalchemy.orm.Mapped` columns.
    """
