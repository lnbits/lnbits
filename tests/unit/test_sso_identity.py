from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi_sso.sso.base import SSOLoginError

from lnbits.core.crud.users import get_account
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
async def test_sso_link_cannot_bypass_password_login(app):
    account = Account(id=uuid4().hex)
    account.hash_password("secret1234")
    await create_user_account(account)
    identity = VerifiedOpenID(
        id="github-user", email=f"{uuid4().hex}@example.com", email_verified=True
    )

    with pytest.raises(HTTPException, match="Sign in with your username and password"):
        await _handle_sso_login(identity, verified_user_id=account.id)

    stored = await get_account(account.id)
    assert stored and stored.password_hash == account.password_hash
    assert not stored.extra.email_verified
