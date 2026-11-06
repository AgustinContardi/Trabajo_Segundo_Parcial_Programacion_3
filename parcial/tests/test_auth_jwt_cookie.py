from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

import jwt
import pytest
from fastapi import Response

from app.core.security import (
    clear_access_token_cookie,
    create_access_token,
    decode_access_token,
    set_access_token_cookie,
)


SECRET = "test-signing-secret-that-is-at-least-32-bytes-long"


def test_access_token_contains_subject_expiration_and_informational_roles() -> None:
    token = create_access_token(
        42, ["ADMIN", "VENDEDOR"], secret=SECRET, ttl_seconds=1800
    )

    payload = jwt.decode(token, SECRET, algorithms=["HS256"])

    assert payload["sub"] == "42"
    assert payload["roles"] == ["ADMIN", "VENDEDOR"]
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()


def test_decode_requires_subject_and_expiration_claims() -> None:
    token = jwt.encode({"sub": "42"}, SECRET, algorithm="HS256")

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token, secret=SECRET)


def test_decode_rejects_expired_or_wrong_signature_tokens() -> None:
    expired = jwt.encode(
        {"sub": "42", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        SECRET,
        algorithm="HS256",
    )
    invalid_signature = create_access_token(
        42, [], secret="another-signing-secret-that-is-also-32-bytes", ttl_seconds=60
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired, secret=SECRET)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(invalid_signature, secret=SECRET)


@pytest.mark.parametrize("secure", [True, False])
def test_access_cookie_attributes_and_empty_body(secure: bool) -> None:
    response = Response()
    token = create_access_token(42, [], secret=SECRET, ttl_seconds=1800)

    set_access_token_cookie(response, token, max_age=1800, secure=secure)

    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    access_cookie = cookie["access_token"]
    assert access_cookie["httponly"]
    assert access_cookie["samesite"] == "lax"
    assert access_cookie["max-age"] == "1800"
    assert bool(access_cookie["secure"]) is secure
    assert access_cookie.value == token
    assert response.body == b""
    assert token.encode() not in response.body


def test_logout_cookie_expires_access_token() -> None:
    response = Response()

    clear_access_token_cookie(response, secure=True)

    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    assert cookie["access_token"]["max-age"] == "0"
    assert cookie["access_token"]["httponly"]
    assert cookie["access_token"]["samesite"] == "lax"
    assert cookie["access_token"]["secure"]
    assert response.body == b""
