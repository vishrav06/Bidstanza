"""
Request and response bodies for registration and login.

`RegisterIn` validates a new account before it reaches the database: usernames are
3–50 characters of letters, digits, `.`, `_` or `-` (the 50 matches the column
width), with surrounding whitespace stripped; passwords are 8–128 characters. The
upper bound caps how much work one argon2 hash can be made to do. Login itself has
no schema here, because it uses FastAPI's `OAuth2PasswordRequestForm` so that the
Swagger "Authorize" button works. `TokenOut` follows the OAuth2 token response
shape (RFC 6749 §5.1), which Swagger and standard clients expect.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$"),
]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterIn(BaseModel):
    username: Username
    password: Password


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds until the token expires
