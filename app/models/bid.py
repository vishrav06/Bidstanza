"""
Bid model: the append-only ledger of every accepted bid.

Each row records who bid how much on which auction, and when. Only accepted bids
are written: the bidding service validates the amount under the auction's row lock
and inserts the bid in the same transaction that moves `current_price`, so the
ledger and the auction can never disagree. Rejected bids leave no trace.

The ledger is immutable. A Postgres trigger, attached right after the table is
created, rejects every UPDATE and DELETE on `bids`, so history cannot be rewritten
by application bugs or by hand-written SQL. Correcting a mistake therefore means
adding new rows, never editing old ones.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DDL, BigInteger, CheckConstraint, ForeignKey, Index, event, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Bid(Base):
    __tablename__ = "bids"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    auction_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("auctions.id"))
    bidder_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal]
    # clock_timestamp(), not now(): now() is frozen at transaction start, so a bid that
    # waited on the auction's row lock would get an earlier timestamp than the bid it
    # waited behind. clock_timestamp() is read at insert time, after the lock is held,
    # so ledger order by created_at always matches the order bids were accepted.
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())

    def __repr__(self) -> str:
        return f"Bid(id={self.id!r}, auction_id={self.auction_id!r}, amount={self.amount!r})"


# Serves "latest bids for an auction" and keyset pagination on (created_at, id).
# id breaks ties so two bids with the same timestamp still sort stably. It's declared
# outside the class because DESC ordering needs the column objects.
Index(
    "ix_bids_auction_id_created_at",
    Bid.auction_id,
    Bid.created_at.desc(),
    Bid.id.desc(),
)


# --------------------------------------------------------------------------- #
# Immutability trigger
# --------------------------------------------------------------------------- #
# Two separate DDL statements, because asyncpg cannot run several commands in one
# execute. `%%` is a literal `%` (DDL text is %-formatted by SQLAlchemy), which
# plpgsql's RAISE then replaces with the operation name.
_reject_mutation_fn = DDL(
    """
    CREATE OR REPLACE FUNCTION bids_reject_mutation() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'bids ledger is immutable: %% is not allowed', TG_OP
            USING ERRCODE = 'restrict_violation';
    END;
    $$ LANGUAGE plpgsql
    """
)
_immutable_trigger = DDL(
    """
    CREATE TRIGGER bids_immutable
    BEFORE UPDATE OR DELETE ON %(table)s
    FOR EACH ROW EXECUTE FUNCTION bids_reject_mutation()
    """
)

# Run right after `create_all` creates the table. Dropping the table drops the trigger;
# the function is left behind but CREATE OR REPLACE makes re-creation safe.
event.listen(Bid.__table__, "after_create", _reject_mutation_fn.execute_if(dialect="postgresql"))
event.listen(Bid.__table__, "after_create", _immutable_trigger.execute_if(dialect="postgresql"))
