"""
User model: an account that can sell auctions and bid on other people's.

A user is identified by a unique `username` and authenticates with a password whose
argon2 hash (never the plain text) is stored in `password_hash`. There is no role
column: any user may create auctions and becomes their seller, and the rule that a
seller cannot bid on their own auction is enforced by the bidding service.

Relationships to auctions and bids are deliberately not declared here. Under async
SQLAlchemy an unexpected lazy load raises instead of silently querying, so services
fetch related rows with explicit queries rather than through ORM attributes.
"""

from datetime import datetime

from sqlalchemy import BigInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # BIGSERIAL
    # unique=True creates `uq_users_username` (via the naming convention); a duplicate
    # insert raises IntegrityError, which the users service maps to `Conflict`.
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Set by Postgres at insert time, so it doesn't depend on the app server's clock.
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        # Excludes password_hash so it can never end up in logs or tracebacks.
        return f"User(id={self.id!r}, username={self.username!r})"
