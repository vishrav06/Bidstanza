"""
ORM models package for Bidstanza.

Importing this package imports every model module, which registers each table on
`Base.metadata`. `create_all` only builds tables it knows about, so the app lifespan
and the test suite import `app.models` before creating the schema; a model left out
here would silently never get a table. The re-exports also give callers one short
import path: `from app.models import Auction, Bid, User`.
"""

from app.models.auction import Auction, AuctionStatus
from app.models.bid import Bid
from app.models.user import User

__all__ = ["Auction", "AuctionStatus", "Bid", "User"]
