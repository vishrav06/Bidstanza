"""
Declarative base for all Bidstanza ORM models.

Every model inherits from `Base`, so its shared `MetaData` is the single registry
that `create_all` uses to build the schema at startup. Two project-wide rules live
here so individual models don't repeat them:

1. A constraint naming convention. Every index, unique, check, foreign key and
   primary key constraint gets a deterministic name such as `ix_bids_bidder_id` or
   `ck_auctions_min_increment_positive`. Postgres error messages then point at
   readable names, and the move to Alembic later produces stable migrations.
2. A type annotation map. Any `Mapped[Decimal]` column becomes NUMERIC(12, 2), and
   any `Mapped[datetime]` column becomes TIMESTAMP WITH TIME ZONE. That enforces
   exact money arithmetic and timezone-aware UTC timestamps across the schema.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, MetaData, Numeric
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all models; holds the shared metadata and type defaults."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    type_annotation_map = {
        Decimal: Numeric(12, 2),            # up to 9,999,999,999.99, exact (no float)
        datetime: DateTime(timezone=True),  # TIMESTAMPTZ: stored as UTC, tz-aware in Python
    }
