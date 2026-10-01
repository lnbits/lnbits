import asyncio

import pytest
from fastapi import FastAPI, HTTPException, Request

from lnbits.core.services.two_factor import (
    code_step,
    decrypt_totp_secret,
    encrypt_totp_secret,
    encryption_key,
    totp,
)
from lnbits.middleware import AuditMiddleware


@pytest.mark.parametrize(
    "timestamp, expected",
    [
        (59, "287082"),
        (1111111109, "081804"),
        (1234567890, "005924"),
        (2000000000, "279037"),
    ],
)
def test_two_factor_rfc6238_vectors(timestamp, expected):
    secret = b"12345678901234567890"
    assert totp(secret).generate(timestamp).decode() == expected
    assert code_step(secret, expected, timestamp, -1) == timestamp // 30
    assert code_step(secret, expected, timestamp, timestamp // 30) is None


@pytest.mark.parametrize("key_bytes", [16, 32])
def test_two_factor_encryption_is_authenticated_and_account_bound(settings, key_bytes):
    settings.totp_encryption_key = "ab" * key_bytes
    secret = b"12345678901234567890"
    encrypted = encrypt_totp_secret("alice", secret)
    assert encrypted != encrypt_totp_secret("alice", secret)
    assert decrypt_totp_secret("alice", encrypted) == secret
    with pytest.raises(HTTPException):
        decrypt_totp_secret("bob", encrypted)
    with pytest.raises(HTTPException):
        decrypt_totp_secret("alice", "AAAA" + encrypted[4:])
    settings.totp_encryption_key = "cd" * key_bytes
    with pytest.raises(HTTPException):
        decrypt_totp_secret("alice", encrypted)


def test_two_factor_generated_key_survives_reload(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "lnbits_data_folder", str(tmp_path))
    monkeypatch.setattr(settings, "totp_encryption_key", "")
    settings.check_totp_encryption_key()
    secret = b"12345678901234567890"
    encrypted = encrypt_totp_secret("alice", secret)
    settings.totp_encryption_key = ""
    settings.check_totp_encryption_key()
    assert decrypt_totp_secret("alice", encrypted) == secret


@pytest.mark.parametrize("key", ["", "1234", "z" * 64])
def test_two_factor_invalid_encryption_key_fails_closed(settings, key):
    settings.totp_encryption_key = key
    with pytest.raises(HTTPException) as exc:
        encryption_key()
    assert exc.value.status_code == 503


def test_two_factor_clock_window():
    secret = b"12345678901234567890"
    assert code_step(secret, totp(secret).generate(300).decode(), 330, -1) == 10
    assert code_step(secret, totp(secret).generate(300).decode(), 360, -1) is None
    assert code_step(secret, "abcdef", 330, -1) is None


@pytest.mark.anyio
async def test_two_factor_audit_omits_credentials(settings):
    settings.lnbits_audit_log_request_body = True
    settings.lnbits_audit_log_query_params = True

    async def receive():
        raise AssertionError("Authentication bodies must never enter audit details")

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/2fa/verify",
            "headers": [],
            "query_string": b"code=private-recovery-code",
        },
        receive,
    )
    middleware = AuditMiddleware(FastAPI(), asyncio.Queue())
    assert await middleware._request_details(request) == "{}"
