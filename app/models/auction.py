"""
Auction model: one item for sale, its live price state and its lifecycle.

An auction is created by a seller with a `starting_price`, a `min_increment` and an
`ends_at` deadline. While it is `active`, the row doubles as the auction's live
state: `current_price` is the highest accepted bid (initialised to the starting
price) and `winner_id` is the current leader, or NULL while no one has bid. The
bidding service updates both under a `SELECT ... FOR UPDATE` row lock, and may push
`ends_at` later (soft close). Settlement flips `status` to `completed` once
`ends_at` has passed, at which point `winner_id` is the final winner.

Price invariants are enforced by CHECK constraints in Postgres, not only in Python,
so no code path (or manual SQL) can store an invalid auction.
"""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuctionStatus(enum.StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class Auction(Base):
    __tablename__ = "auctions"
    __table_args__ = (
        # Names expand via the naming convention, e.g. `ck_auctions_starting_price_positive`.
        CheckConstraint("starting_price > 0", name="starting_price_positive"),
        CheckConstraint("min_increment > 0", name="min_increment_positive"),
        CheckConstraint("current_price >= starting_price", name="current_price_gte_starting"),
        # Serves the settlement query: WHERE status = 'active' AND ends_at <= now().
        Index("ix_auctions_status_ends_at", "status", "ends_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # BigInteger is explicit on FKs so they match the BIGSERIAL `users.id`.
    seller_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    starting_price: Mapped[Decimal]
    min_increment: Mapped[Decimal]
    current_price: Mapped[Decimal]

    # Stored as a native Postgres enum `auction_status` holding the lowercase values.
    status: Mapped[AuctionStatus] = mapped_column(
        Enum(
            AuctionStatus,
            name="auction_status",
            values_callable=lambda members: [m.value for m in members],
        ),
        default=AuctionStatus.ACTIVE,
        server_default=AuctionStatus.ACTIVE.value,
    )
    # Current leader while active, final winner once completed; NULL means no bids.
    winner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))

    ends_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # onupdate=func.now() makes every ORM UPDATE (bid, settlement) refresh this column.
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"Auction(id={self.id!r}, status={self.status!r}, current_price={self.current_price!r})"
