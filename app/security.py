import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.config import settings

ALGORITHM = "HS256"
ISSUER = "worksphere-api"
AUDIENCE = "worksphere-client"
password_hasher = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": expires_at,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> UUID:
    claims = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={"require": ["sub", "iss", "aud", "iat", "exp"]},
    )
    subject = claims["sub"]
    if not isinstance(subject, str):
        raise ValueError("Token subject must be a string.")
    return UUID(subject)


def create_csrf_token(session_token: str) -> str:
    secret = settings.jwt_secret_key.get_secret_value().encode()
    return hmac.new(secret, session_token.encode(), hashlib.sha256).hexdigest()


def verify_csrf_token(
    session_token: str, cookie_token: str | None, header_token: str | None
) -> bool:
    if cookie_token is None or header_token is None:
        return False
    expected_token = create_csrf_token(session_token)
    return hmac.compare_digest(cookie_token, expected_token) and hmac.compare_digest(
        header_token, expected_token
    )
