"""
Public representation of a user.

`UserOut` is the only shape in which a user ever leaves the API: registration,
`GET /users/me` and `GET /users/{id}` all return it, and the auction and bid schemas
reuse the same id and username fields. It lists exactly the fields that are safe to
expose. Because a response model drops everything it doesn't declare,
`password_hash` cannot leak even when a route returns the ORM `User` object directly.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    # from_attributes lets FastAPI build this straight from a SQLAlchemy `User`.
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime
