import base64
from http import HTTPStatus
from time import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from lnbits.core.crud.two_factor import get_two_factor_config
from lnbits.core.crud.users import get_account
from lnbits.core.models.two_factor import (
    TwoFactorCode,
    TwoFactorConfig,
    TwoFactorStatus,
)
from lnbits.core.models.users import AccessTokenPayload, Account
from lnbits.core.services.two_factor import (
    begin_enrollment,
    check_two_factor_session,
    mutate_config,
    new_recovery_codes,
    require_recent_login,
    session_payload,
    totp,
    two_factor_error,
    validate_identity,
    verify_factor,
)
from lnbits.decorators import _decode_access_token
from lnbits.settings import settings

two_factor_router = APIRouter(prefix="/api/v1/auth/2fa", tags=["Two Factor Auth"])


async def two_factor_identity(request: Request) -> tuple[Account, AccessTokenPayload]:
    # Challenge cookies never participate in ordinary account authentication.
    token: str | None = request.headers.get("Authorization", "").removeprefix("Bearer ")
    token = token or request.cookies.get("two_factor_challenge")
    token = token or request.cookies.get("cookie_access_token")
    if not token:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Please log in first.")
    payload = _decode_access_token(token)
    account = await get_account(payload.usr or "")
    if not account and payload.sub:
        from lnbits.core.crud.users import get_account_by_username

        account = await get_account_by_username(payload.sub)
    if not account:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Please log in again.")
    config, _ = await get_two_factor_config(account.id)
    validate_identity(config, payload)
    if not settings.is_user_allowed(account.id):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Account access is disabled.")
    return account, payload


async def factor_session_response(
    account: Account,
    config: TwoFactorConfig,
    verified: bool,
    codes: list[str] | None = None,
) -> JSONResponse:
    from lnbits.core.views.auth_api import _auth_success_response

    payload = await session_payload(account.id, config, verified)
    response = _auth_success_response(payload=payload, recovery_codes=codes)
    response.delete_cookie("two_factor_challenge")
    response.headers["Cache-Control"] = "no-store"
    return response


@two_factor_router.get("/status")
async def factor_status(
    identity: tuple[Account, AccessTokenPayload] = Depends(two_factor_identity),
) -> TwoFactorStatus:
    account, payload = identity
    config, _ = await get_two_factor_config(account.id)
    return TwoFactorStatus(
        available=settings.lnbits_two_factor_enabled,
        mandatory=settings.lnbits_two_factor_mandatory,
        enrolled=bool(config.secret),
        challenge=payload.purpose == "two_factor",
        recovery_remaining=len(config.recovery_hashes),
        recovery_saved=config.recovery_saved,
    )


@two_factor_router.post("/setup")
async def setup_factor(
    identity: tuple[Account, AccessTokenPayload] = Depends(two_factor_identity),
) -> JSONResponse:
    account, payload = identity
    secret = await begin_enrollment(account.id, payload)
    uri = totp(secret).get_provisioning_uri(
        account.username or account.email or account.id, settings.lnbits_site_title
    )
    return JSONResponse(
        {"secret": base64.b32encode(secret).decode(), "uri": uri},
        headers={"Cache-Control": "no-store"},
    )


@two_factor_router.post("/confirm")
async def confirm_factor(
    data: TwoFactorCode,
    identity: tuple[Account, AccessTokenPayload] = Depends(two_factor_identity),
) -> JSONResponse:
    if not settings.lnbits_two_factor_enabled:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Two factor authentication is disabled."
        )
    account, payload = identity
    require_recent_login(payload)
    config, codes = await verify_factor(account.id, payload, data.code, enrolling=True)
    return await factor_session_response(account, config, True, codes)


@two_factor_router.post("/verify")
async def verify_two_factor(
    data: TwoFactorCode,
    identity: tuple[Account, AccessTokenPayload] = Depends(two_factor_identity),
) -> JSONResponse:
    if not settings.lnbits_two_factor_enabled:
        raise two_factor_error(
            "Two factor authentication is disabled. Please log in again."
        )
    account, payload = identity
    config, _ = await verify_factor(account.id, payload, data.code)
    return await factor_session_response(account, config, True)


async def recent_factor_identity(
    identity: tuple[Account, AccessTokenPayload] = Depends(two_factor_identity),
) -> tuple[Account, AccessTokenPayload]:
    account, payload = identity
    require_recent_login(payload)
    await check_two_factor_session(account.id, payload, "/api/v1/auth/2fa", "POST")
    return identity


@two_factor_router.post("/recovery/acknowledge")
async def acknowledge_recovery(
    identity: tuple[Account, AccessTokenPayload] = Depends(recent_factor_identity),
):
    account, payload = identity

    def acknowledge(config: TwoFactorConfig):
        validate_identity(config, payload)
        config.recovery_saved = True

    await mutate_config(account.id, acknowledge)
    return {"status": "success"}


@two_factor_router.post("/recovery")
async def regenerate_recovery(
    identity: tuple[Account, AccessTokenPayload] = Depends(recent_factor_identity),
) -> JSONResponse:
    account, payload = identity

    def regenerate(config: TwoFactorConfig):
        validate_identity(config, payload)
        if not config.secret:
            raise HTTPException(HTTPStatus.BAD_REQUEST, "No authenticator enrolled.")
        return new_recovery_codes(config)

    _, codes = await mutate_config(account.id, regenerate)
    return JSONResponse(
        {"recovery_codes": codes}, headers={"Cache-Control": "no-store"}
    )


@two_factor_router.delete("")
async def disable_factor(
    identity: tuple[Account, AccessTokenPayload] = Depends(recent_factor_identity),
) -> JSONResponse:
    import secrets

    from loguru import logger

    if settings.lnbits_two_factor_enabled and settings.lnbits_two_factor_mandatory:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "Two factor authentication is mandatory."
        )
    account, payload = identity

    def disable(config: TwoFactorConfig):
        validate_identity(config, payload)
        replacement = TwoFactorConfig(revision=secrets.token_hex(16))
        for field, value in replacement.dict().items():
            setattr(config, field, value)

    config, _ = await mutate_config(account.id, disable)
    logger.info("Two factor disabled for account {} at {}", account.id, int(time()))
    return await factor_session_response(account, config, False)
