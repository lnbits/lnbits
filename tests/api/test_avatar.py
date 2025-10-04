"""API tests for avatar endpoints (excluding file upload tests)."""

import pytest
from httpx import AsyncClient

from lnbits.core.crud.users import get_account, update_account
from lnbits.core.models.users import UserExtra


@pytest.fixture(scope="function")
async def authed_headers(http_client: AsyncClient, from_user):
    """Fixture that provides auth headers with access token."""
    # Login to get access token
    response = await http_client.post("/api/v1/auth/usr", json={"usr": from_user.id})
    if response.status_code != 200:
        print(f"Login failed: {response.status_code} - {response.json()}")
    assert response.status_code == 200, f"Login failed: {response.json()}"
    access_token = response.json().get("access_token")
    assert access_token is not None, "No access token in response"
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.anyio
async def test_get_avatar_no_picture(
    http_client: AsyncClient, authed_headers, from_user
):
    """Test getting avatar returns 404 when no picture set."""
    response = await http_client.get("/api/v1/auth/avatar", headers=authed_headers)
    assert response.status_code == 404
    assert "No avatar" in response.json()["detail"]


@pytest.mark.anyio
async def test_get_avatar_external_url(
    http_client: AsyncClient, authed_headers, from_user
):
    """Test getting avatar returns external URL."""
    # Set an external picture URL
    account = await get_account(from_user.id)
    assert account is not None
    if not account.extra:
        account.extra = UserExtra()
    account.extra.picture = "https://example.com/avatar.jpg"
    await update_account(account)

    response = await http_client.get("/api/v1/auth/avatar", headers=authed_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://example.com/avatar.jpg"


@pytest.mark.anyio
async def test_delete_avatar_not_found(
    http_client: AsyncClient, authed_headers, from_user
):
    """Test deleting avatar returns 404 when no avatar exists."""
    # Ensure no avatar is set
    account = await get_account(from_user.id)
    if account and account.extra:
        account.extra.picture = None
        await update_account(account)

    response = await http_client.delete("/api/v1/auth/avatar", headers=authed_headers)
    assert response.status_code == 404
    assert "No avatar" in response.json()["detail"]


@pytest.mark.anyio
async def test_delete_avatar_external_url(
    http_client: AsyncClient, authed_headers, from_user
):
    """Test deleting avatar clears external URL."""
    # Set an external picture URL
    account = await get_account(from_user.id)
    assert account is not None
    if not account.extra:
        account.extra = UserExtra()
    account.extra.picture = "https://example.com/avatar.jpg"
    await update_account(account)

    # Delete avatar
    response = await http_client.delete("/api/v1/auth/avatar", headers=authed_headers)
    assert response.status_code == 200

    # Verify picture field was cleared by fetching from database
    account = await get_account(from_user.id)
    assert account is not None
    assert account.extra is not None
    assert account.extra.picture is None


@pytest.mark.anyio
async def test_avatar_requires_authentication(http_client):
    """Test avatar endpoints require authentication."""
    # Try to get avatar without auth
    response = await http_client.get("/api/v1/auth/avatar")
    assert response.status_code == 401

    # Try to delete avatar without auth
    response = await http_client.delete("/api/v1/auth/avatar")
    assert response.status_code == 401
