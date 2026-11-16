from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from fastapi_sso.sso.base import SSOLoginError

from lnbits.core.crud.sso import get_account_by_sso, link_sso_identity
from lnbits.core.crud.users import (
    create_account,
    delete_account,
    delete_accounts_no_wallets,
    get_account,
    update_account,
)
from lnbits.core.db import db
from lnbits.core.models.sso import VerifiedOpenID
from lnbits.core.models.sso.github import GithubSSO
from lnbits.core.models.sso.google import GoogleSSO
from lnbits.core.models.sso.keycloak import KeycloakSSO
from lnbits.core.models.sso.oidc import OidcSSO
from lnbits.core.models.users import Account, UpdateUser, UserExtra
from lnbits.core.services.users import create_user_account
from lnbits.core.views.auth_api import _handle_sso_login, update


@pytest.mark.anyio
@pytest.mark.parametrize("provider", [GoogleSSO, KeycloakSSO, OidcSSO])
@pytest.mark.parametrize("verified", [None, False, "true", 1])
async def test_sso_providers_reject_unverified_email(provider, verified):
    sso = provider("client", "secret")
    with pytest.raises(SSOLoginError):
        await sso.openid_from_response(
            {"sub": "subject", "email": "owner@example.com", "email_verified": verified}
        )


@pytest.mark.anyio
@pytest.mark.parametrize("provider", [GoogleSSO, KeycloakSSO, OidcSSO])
async def test_sso_providers_preserve_verified_identity(provider):
    identity = await provider("client", "secret").openid_from_response(
        {"sub": "subject", "email": "owner@example.com", "email_verified": True}
    )
    assert isinstance(identity, VerifiedOpenID)
    assert identity.email_verified and identity.id == "subject"


@pytest.mark.anyio
@pytest.mark.parametrize("verified", [False, True])
async def test_github_checks_primary_email_even_with_a_public_profile_email(verified):
    def handler(request):
        assert str(request.url) == "https://api.github.com/user/emails"
        return httpx.Response(
            200,
            json=[
                {"email": "owner@example.com", "primary": True, "verified": verified}
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as session:
        sso = GithubSSO("client", "secret")
        response = {
            "id": 123,
            "login": "owner",
            "avatar_url": None,
            "email": "unverified@example.com",
        }
        if not verified:
            with pytest.raises(SSOLoginError):
                await sso.openid_from_response(response, session)
        else:
            identity = await sso.openid_from_response(response, session)
            assert identity.email == "owner@example.com"
            assert identity.email_verified and identity.id == "123"


@pytest.mark.anyio
async def test_sso_cannot_claim_an_unverified_local_account(app, mocker):
    account = Account(
        id=uuid4().hex,
        email=f"{uuid4().hex}@example.com",
        username=f"u_{uuid4().hex[:10]}",
    )
    account.hash_password("attacker-password")
    await create_user_account(account)
    login = mocker.patch("lnbits.core.views.auth_api._login_response")
    identity = _identity(account.email)
    assert identity.id

    with pytest.raises(HTTPException, match="Sign in to your existing account"):
        await _handle_sso_login(identity, provider="google")

    login.assert_not_called()
    stored = await get_account(account.id)
    assert stored and not stored.extra.email_verified
    assert await get_account_by_sso("google", identity.id) is None


@pytest.mark.anyio
async def test_sso_migrates_verified_accounts_then_uses_subject_not_email(app, mocker):
    account = Account(
        id=uuid4().hex,
        email=f"{uuid4().hex}@example.com",
        extra=UserExtra(email_verified=True),
    )
    await create_user_account(account)
    login = mocker.patch(
        "lnbits.core.views.auth_api._login_response", return_value=JSONResponse({})
    )
    identity = _identity(account.email)
    assert identity.id
    await _handle_sso_login(identity, provider="google")
    linked = await get_account_by_sso("google", identity.id)
    assert linked and linked.id == account.id

    changed_email = identity.model_copy(update={"email": f"{uuid4().hex}@example.com"})
    await _handle_sso_login(changed_email, provider="google")
    assert login.call_args.args[0].id == account.id

    with pytest.raises(HTTPException, match="Sign in to your existing account"):
        await _handle_sso_login(_identity(account.email), provider="google")


@pytest.mark.anyio
async def test_sso_explicit_link_requires_the_same_account_and_preserves_password(
    app, mocker
):
    account = Account(id=uuid4().hex, email=f"{uuid4().hex}@example.com")
    account.hash_password("local-password")
    await create_user_account(account)
    mocker.patch(
        "lnbits.core.views.auth_api._login_response", return_value=JSONResponse({})
    )
    identity = _identity(account.email)
    assert identity.id

    response = await _handle_sso_login(identity, account.id, provider="google")

    assert response.headers["location"] == "/account"
    stored = await get_account(account.id)
    assert stored and stored.extra.email_verified
    assert stored.password_hash == account.password_hash
    other = Account(id=uuid4().hex, email=f"{uuid4().hex}@example.com")
    await create_user_account(other)
    with pytest.raises(HTTPException, match="SSO identity already linked"):
        await _handle_sso_login(identity, other.id, provider="google")
    with pytest.raises(ValueError, match="already linked"):
        await link_sso_identity("google", identity.id, other.id)


@pytest.mark.anyio
async def test_sso_identity_is_scoped_to_provider_and_rejects_deactivated_accounts(
    app, mocker
):
    mocker.patch(
        "lnbits.core.views.auth_api._login_response", return_value=JSONResponse({})
    )
    identity = _identity(f"{uuid4().hex}@example.com")
    assert identity.id
    await _handle_sso_login(identity, provider="google")
    google_account = await get_account_by_sso("google", identity.id)
    assert google_account
    github_identity = identity.model_copy(
        update={"email": f"{uuid4().hex}@example.com"}
    )
    await _handle_sso_login(github_identity, provider="github")
    github_account = await get_account_by_sso("github", identity.id)
    assert github_account and github_account.id != google_account.id

    google_account.activated = False
    await update_account(google_account)
    with pytest.raises(HTTPException, match="deactivated"):
        await _handle_sso_login(identity, provider="google")


@pytest.mark.anyio
async def test_sso_identity_is_scoped_to_oidc_configuration(app, mocker, settings):
    mocker.patch(
        "lnbits.core.views.auth_api._login_response", return_value=JSONResponse({})
    )
    identity = _identity(f"{uuid4().hex}@example.com")
    assert identity.id
    settings.oidc_discovery_url = (
        "https://first.example.com/.well-known/openid-configuration"
    )
    await _handle_sso_login(identity, provider="oidc")
    first = await get_account_by_sso(f"oidc:{settings.oidc_discovery_url}", identity.id)
    settings.oidc_discovery_url = (
        "https://second.example.com/.well-known/openid-configuration"
    )
    identity.email = f"{uuid4().hex}@example.com"
    await _handle_sso_login(identity, provider="oidc")
    second = await get_account_by_sso(
        f"oidc:{settings.oidc_discovery_url}", identity.id
    )
    assert first and second and first.id != second.id


@pytest.mark.anyio
async def test_profile_update_cannot_verify_email(app):
    account = Account(id=uuid4().hex, email=f"{uuid4().hex}@example.com")
    await create_user_account(account)
    await update(
        UpdateUser(
            user_id=account.id, username=None, extra=UserExtra(email_verified=True)
        ),
        account,
    )
    stored = await get_account(account.id)
    assert stored and stored.extra.email_verified is False


@pytest.mark.anyio
@pytest.mark.parametrize("cleanup", ["delete", "prune"])
async def test_sso_identity_is_removed_with_its_account(app, cleanup):
    account = Account(
        id=uuid4().hex, updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc)
    )
    await create_account(account)
    subject = uuid4().hex
    await link_sso_identity("google", subject, account.id)

    if cleanup == "delete":
        await delete_account(account.id)
    else:
        await delete_accounts_no_wallets(0)

    assert await get_account(account.id) is None
    assert not await db.fetchone(
        "SELECT user_id FROM sso_identities WHERE user_id = :id", {"id": account.id}
    )
    replacement = await create_account(Account(id=uuid4().hex))
    await link_sso_identity("google", subject, replacement.id)
    linked = await get_account_by_sso("google", subject)
    assert linked and linked.id == replacement.id


def _identity(email: str | None) -> VerifiedOpenID:
    assert email is not None
    return VerifiedOpenID(id=uuid4().hex, email=email, email_verified=True)
