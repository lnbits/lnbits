import base64
import json
import secrets
from collections.abc import Callable
from hashlib import sha256
from http import HTTPStatus
from time import time
from typing import TypeVar

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from fastapi import HTTPException
from loguru import logger

from lnbits.core.crud.settings import get_settings_field, set_settings_field
from lnbits.core.crud.two_factor import (
    get_two_factor_config,
    get_two_factor_policy_revision,
    save_two_factor_config,
)
from lnbits.core.models.two_factor import TwoFactorConfig
from lnbits.core.models.users import AccessTokenPayload
from lnbits.db import Connection
from lnbits.settings import UpdateSettings, settings

T = TypeVar("T")
CHALLENGE_SECONDS = 300
FAILURE_WINDOW = 900
FAILURE_LIMIT = 5


def two_factor_error(message: str = "Two factor verification required."):
    return HTTPException(
        HTTPStatus.UNAUTHORIZED, message, headers={"two-factor-required": "true"}
    )


def encryption_key() -> bytes:
    try:
        key = bytes.fromhex(settings.totp_encryption_key)
        if len(key) in (16, 32):
            return key
    except ValueError:
        pass
    raise HTTPException(
        HTTPStatus.SERVICE_UNAVAILABLE,
        "Two factor authentication requires a valid TOTP_ENCRYPTION_KEY.",
    )


def encrypt_totp_secret(user_id: str, secret: bytes) -> str:
    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(encryption_key()).encrypt(nonce, secret, user_id.encode())
    return base64.urlsafe_b64encode(nonce + encrypted).decode()


def decrypt_totp_secret(user_id: str, encrypted: str) -> bytes:
    key = encryption_key()
    try:
        data = base64.urlsafe_b64decode(encrypted)
        return AESGCM(key).decrypt(data[:12], data[12:], user_id.encode())
    except (InvalidTag, ValueError) as exc:
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "Unable to unlock the authenticator. Contact the operator.",
        ) from exc


def totp(secret: bytes) -> TOTP:
    # HMAC-SHA1 is the interoperable RFC 6238 default, not a password hash.
    return TOTP(secret, 6, SHA1(), 30)  # noqa: S303


def code_step(secret: bytes, code: str, now: int, last_step: int) -> int | None:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    current_step = now // 30
    for step in (current_step, current_step - 1, current_step + 1):
        if step > last_step and secrets.compare_digest(
            totp(secret).generate(step * 30), code.encode()
        ):
            return step
    return None


async def mutate_config(
    user_id: str, action: Callable[[TwoFactorConfig], T]
) -> tuple[TwoFactorConfig, T]:
    for _ in range(10):
        config, raw = await get_two_factor_config(user_id)
        result = action(config)
        if await save_two_factor_config(user_id, config, raw):
            return config, result
    raise HTTPException(HTTPStatus.CONFLICT, "Authentication changed. Try again.")


def validate_identity(config: TwoFactorConfig, payload: AccessTokenPayload) -> None:
    if payload.api_token_id or payload.impersonated_by:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Use your own interactive login.")
    if payload.mfa_revision != config.revision:
        raise two_factor_error("Account security changed. Please log in again.")
    if payload.purpose == "two_factor":
        if not payload.jti or config.challenges.get(payload.jti, 0) <= time():
            raise two_factor_error("Verification expired. Please log in again.")
    elif payload.purpose != "session":
        raise two_factor_error()


def require_recent_login(payload: AccessTokenPayload) -> None:
    if time() - (payload.auth_time or 0) > settings.auth_credetials_update_threshold:
        raise HTTPException(
            HTTPStatus.UNAUTHORIZED,
            "Please log in again before changing account security.",
            headers={"token-expired": "true"},
        )


async def issue_challenge(user_id: str) -> AccessTokenPayload:
    challenge_id = secrets.token_hex(24)
    now = int(time())

    def issue(config: TwoFactorConfig):
        config.challenges = {
            key: expires for key, expires in config.challenges.items() if expires > now
        }
        # Bound storage without resetting the persistent account attempt counter.
        config.challenges = dict(list(config.challenges.items())[-4:])
        config.challenges[challenge_id] = now + CHALLENGE_SECONDS

    config, _ = await mutate_config(user_id, issue)
    return AccessTokenPayload(
        sub="",
        usr=user_id,
        auth_time=now,
        purpose="two_factor",
        jti=challenge_id,
        mfa_revision=config.revision,
    )


async def begin_enrollment(user_id: str, payload: AccessTokenPayload) -> bytes:
    if not settings.lnbits_two_factor_enabled:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Two factor authentication is disabled."
        )
    require_recent_login(payload)
    secret = secrets.token_bytes(20)
    encrypted = encrypt_totp_secret(user_id, secret)

    def begin(config: TwoFactorConfig):
        validate_identity(config, payload)
        if config.secret:
            raise HTTPException(
                HTTPStatus.CONFLICT, "An authenticator is already enrolled."
            )
        config.pending_secret = encrypted
        config.pending_until = int(time()) + CHALLENGE_SECONDS

    await mutate_config(user_id, begin)
    return secret


def new_recovery_codes(config: TwoFactorConfig) -> list[str]:
    codes = [secrets.token_hex(10) for _ in range(10)]
    config.recovery_hashes = [sha256(code.encode()).hexdigest() for code in codes]
    config.recovery_saved = False
    return codes


async def verify_factor(
    user_id: str, payload: AccessTokenPayload, code: str, enrolling: bool = False
) -> tuple[TwoFactorConfig, list[str]]:
    now = int(time())

    def verify(config: TwoFactorConfig) -> tuple[bool, list[str]]:
        validate_identity(config, payload)
        _record_attempt(config, now)
        encrypted = config.pending_secret if enrolling else config.secret
        if not encrypted or (
            enrolling and (config.secret or config.pending_until < now)
        ):
            return False, []
        step = code_step(
            decrypt_totp_secret(user_id, encrypted), code, now, config.last_step
        )
        recovery_hash = sha256(code.strip().lower().encode()).hexdigest()
        recovery = not enrolling and recovery_hash in config.recovery_hashes
        if step is None and not recovery:
            return False, []
        if recovery:
            config.recovery_hashes.remove(recovery_hash)
        else:
            config.last_step = step if step is not None else config.last_step
        codes: list[str] = []
        if enrolling:
            config.secret = config.pending_secret
            config.pending_secret = None
            config.pending_until = 0
            config.revision = secrets.token_hex(16)
            config.challenges = {}
            codes = new_recovery_codes(config)
        elif payload.jti:
            config.challenges.pop(payload.jti, None)
        config.failures = 0
        config.failure_window = 0
        return True, codes

    config, (valid, codes) = await mutate_config(user_id, verify)
    if not valid:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Invalid or already used code.")
    logger.info(
        "Two factor {} for account {}", "enrolled" if enrolling else "verified", user_id
    )
    return config, codes


def _record_attempt(config: TwoFactorConfig, now: int) -> None:
    if now >= config.failure_window + FAILURE_WINDOW:
        config.failures = 0
        config.failure_window = now
    if config.failures >= FAILURE_LIMIT:
        raise HTTPException(
            HTTPStatus.TOO_MANY_REQUESTS, "Too many codes. Try again later."
        )
    config.failures += 1


async def session_payload(
    user_id: str, config: TwoFactorConfig, verified: bool = False
) -> AccessTokenPayload:
    return AccessTokenPayload(
        sub="",
        usr=user_id,
        auth_time=int(time()),
        mfa_revision=config.revision,
        mfa_time=int(time()) if verified else 0,
        mfa_policy=await get_two_factor_policy_revision(),
    )


async def sync_two_factor_policy() -> str:
    """Invalidate old MFA claims when policy changes, including via environment."""
    fingerprint = json.dumps(
        [
            settings.lnbits_two_factor_enabled,
            sorted(settings.lnbits_two_factor_methods),
            settings.lnbits_two_factor_mandatory,
        ]
    )
    previous = await get_settings_field("two_factor_policy", "security")
    if previous and previous.value == fingerprint:
        return await get_two_factor_policy_revision()
    revision = secrets.token_hex(16)
    await set_settings_field("two_factor_revision", revision, "security")
    await set_settings_field("two_factor_policy", fingerprint, "security")
    return revision


def security_operation(path: str, method: str) -> bool:
    if path.rstrip("/") == "/api/v1/auth/impersonate" and method == "DELETE":
        return False
    if method == "GET" and (
        path
        in {
            "/api/v1/auth/google",
            "/api/v1/auth/github",
            "/api/v1/auth/keycloak",
            "/api/v1/auth/oidc",
        }
        or path.endswith("/reset_password")
    ):
        return True
    if method in {"GET", "HEAD", "OPTIONS"}:
        return False
    return path.rstrip("/") == "/api/v1/auth" or path.startswith(
        (
            "/api/v1/auth/password",
            "/api/v1/auth/pubkey",
            "/api/v1/auth/acl",
            "/api/v1/auth/impersonate",
            "/api/v1/auth/2fa",
            "/admin/api/v1/settings",
            "/users/api/v1/user",
        )
    )


async def check_two_factor_session(
    user_id: str,
    payload: AccessTokenPayload | None,
    path: str,
    method: str,
    conn: Connection | None = None,
) -> None:
    sensitive = security_operation(path, method)
    if payload and payload.purpose != "session":
        raise two_factor_error()
    if payload and payload.api_token_id:
        if sensitive and (settings.lnbits_two_factor_enabled or "/2fa" in path):
            raise HTTPException(
                HTTPStatus.FORBIDDEN, "Interactive authentication required."
            )
        return
    actor = payload.impersonated_by if payload else None
    if actor and (sensitive or not settings.is_admin_user(actor)):
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Impersonation cannot change account security."
        )
    if not settings.lnbits_two_factor_enabled and not (
        payload and payload.mfa_revision
    ):
        return
    config, _ = await get_two_factor_config(actor or user_id, conn)
    if payload and config.revision != payload.mfa_revision:
        raise two_factor_error("Account security changed. Please log in again.")
    required = (
        bool(config.secret)
        or settings.lnbits_two_factor_mandatory
        or (path.rstrip("/") == "/api/v1/auth/impersonate" and method == "POST")
    )
    if not settings.lnbits_two_factor_enabled or not required:
        return
    if (
        not payload
        or not config.secret
        or not payload.mfa_time
        or payload.mfa_policy != await get_two_factor_policy_revision(conn)
    ):
        raise two_factor_error()
    if (
        sensitive
        and time() - payload.mfa_time > settings.auth_credetials_update_threshold
    ):
        raise two_factor_error("Fresh two factor verification required.")


async def reset_two_factor(user_id: str) -> None:
    def reset(config: TwoFactorConfig):
        replacement = TwoFactorConfig(revision=secrets.token_hex(16))
        for field, value in replacement.dict().items():
            setattr(config, field, value)

    await mutate_config(user_id, reset)
    logger.warning("Two factor reset locally for account {}", user_id)


async def validate_two_factor_policy(
    data: UpdateSettings, account_id: str, payload: AccessTokenPayload
) -> bool:
    fields = (
        "lnbits_two_factor_enabled",
        "lnbits_two_factor_methods",
        "lnbits_two_factor_mandatory",
    )
    if not any(getattr(data, field) != getattr(settings, field) for field in fields):
        return False
    require_recent_login(payload)
    if payload.api_token_id or payload.impersonated_by:
        raise HTTPException(HTTPStatus.FORBIDDEN, "Use your own interactive login.")
    if data.lnbits_two_factor_enabled:
        encryption_key()
        if "totp" not in data.lnbits_two_factor_methods:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST, "Select at least one two factor method."
            )
        if data.lnbits_two_factor_mandatory:
            config, _ = await get_two_factor_config(account_id)
            if not config.secret or not config.recovery_saved:
                raise HTTPException(
                    HTTPStatus.BAD_REQUEST,
                    "Enroll your authenticator and save recovery codes "
                    "before requiring 2FA.",
                )
            if time() - payload.mfa_time > settings.auth_credetials_update_threshold:
                raise two_factor_error(
                    "Verify your authenticator before requiring 2FA."
                )
    return True
