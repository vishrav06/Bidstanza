"""
Password hashing and JWT access tokens for Bidstanza.

Passwords are hashed with argon2 through pwdlib's recommended settings; only the
hash is stored, and verification is constant-time. `verify_password` also accepts
`None` for a user that doesn't exist and still runs a full hash check, so a login
for an unknown username takes as long as one with a wrong password. Response timing
therefore doesn't reveal which usernames are registered.

Access tokens are short-lived HS256 JWTs with `sub` (the user id, as a string),
`iat` and `exp` claims. `decode_access_token` turns every way a token can be bad
(expired, tampered, wrong algorithm, missing claims, malformed) into the same
`Unauthorized` error, so callers only ever handle one failure.
"""

from datetime import UTC, datetime

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.errors import Unauthorized

_hasher = PasswordHash.recommended()  # argon2id with pwdlib's current defaults

# Verified against when the user doesn't exist, so that path costs a real argon2 check.
_DUMMY_HASH = _hasher.hash("bidstanza-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """True if `password` matches; pass `None` when the user wasn't found."""
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),  # RFC 7519 requires a string; PyJWT enforces it
        "iat": now,
        "exp": now + settings.access_token_ttl,
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    """Return the user id from a valid token, or raise `Unauthorized`."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            # A fixed list, never the token's own header, blocks `alg: none` and
            # algorithm-confusion attacks.
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
        return int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        # InvalidTokenError covers expired, bad signature, malformed and missing claims.
        raise Unauthorized("Invalid or expired access token.") from None
