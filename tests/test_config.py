import pytest
from pydantic import ValidationError

from app.config import Settings


def test_signing_key_must_be_at_least_32_characters() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret_key="too-short")


def test_access_token_expiry_must_be_between_one_minute_and_one_day() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            jwt_secret_key="test-only-signing-key-for-worksphere-tests-1234567890",
            access_token_expire_minutes=0,
        )

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            jwt_secret_key="test-only-signing-key-for-worksphere-tests-1234567890",
            access_token_expire_minutes=1441,
        )
