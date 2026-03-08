from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture

from lnbits.core.services.settings import (
    check_webpush_settings,
    dict_to_settings,
    update_cached_settings,
)
from lnbits.settings import Settings


class FakePublicKey:
    def public_bytes(self, *_args, **_kwargs):
        return b"public-bytes"


class FakeVapid:
    def __init__(self, has_public_key: bool = True):
        self.public_key = FakePublicKey() if has_public_key else None

    def generate_keys(self):
        return None

    def private_pem(self):
        return b"private-key"


def test_dict_to_settings_parses_known_values():
    parsed = dict_to_settings(
        {
            "lnbits_site_title": "Test Title",
            "lnbits_service_fee": 5,
            "ignored_field": "ignored",
        }
    )

    assert parsed.lnbits_site_title == "Test Title"
    assert parsed.lnbits_service_fee == 5
    assert not hasattr(parsed, "ignored_field")


def test_dict_to_settings_validates_invalid_values():
    with pytest.raises(ValidationError):
        dict_to_settings({"lnbits_service_fee": "not-a-number"})


def test_update_cached_settings_updates_runtime_values(settings: Settings):
    original_title = settings.lnbits_site_title
    original_host = settings.host
    original_super_user = settings.super_user
    try:
        update_cached_settings(
            {
                "lnbits_site_title": "Updated",
                "host": "forbidden-host",
                "super_user": "super-user-id",
                "missing_field": "ignored",
            }
        )

        assert settings.lnbits_site_title == "Updated"
        assert settings.host == original_host
        assert settings.super_user == "super-user-id"
    finally:
        settings.lnbits_site_title = original_title
        settings.host = original_host
        settings.super_user = original_super_user


@pytest.mark.anyio
async def test_check_webpush_settings_generates_and_persists_keys(
    settings: Settings, mocker: MockerFixture
):
    mocker.patch.object(settings, "lnbits_webpush_privkey", "")
    mocker.patch.object(settings, "lnbits_webpush_pubkey", None)
    mocker.patch.object(settings, "lnbits_admin_ui", True)
    mocker.patch("lnbits.core.services.settings.Vapid", return_value=FakeVapid())
    mocker.patch("lnbits.core.services.settings.b64urlencode", return_value="public-key")
    update_admin = mocker.patch(
        "lnbits.core.services.settings.update_admin_settings",
        AsyncMock(),
    )

    await check_webpush_settings()

    assert settings.lnbits_webpush_privkey == "private-key"
    assert settings.lnbits_webpush_pubkey == "public-key"
    update_admin.assert_awaited_once()


@pytest.mark.anyio
async def test_check_webpush_settings_requires_public_key(
    settings: Settings, mocker: MockerFixture
):
    mocker.patch.object(settings, "lnbits_webpush_privkey", "")
    mocker.patch.object(settings, "lnbits_admin_ui", False)
    mocker.patch(
        "lnbits.core.services.settings.Vapid",
        return_value=FakeVapid(has_public_key=False),
    )

    with pytest.raises(ValueError, match="VAPID public key does not exist"):
        await check_webpush_settings()


@pytest.mark.anyio
async def test_check_webpush_settings_skips_generation_when_keys_exist(
    settings: Settings, mocker: MockerFixture
):
    mocker.patch.object(settings, "lnbits_webpush_privkey", "existing-private-key")
    mocker.patch.object(settings, "lnbits_webpush_pubkey", "existing-public-key")
    vapid = mocker.patch("lnbits.core.services.settings.Vapid")
    update_admin = mocker.patch(
        "lnbits.core.services.settings.update_admin_settings",
        AsyncMock(),
    )

    await check_webpush_settings()

    vapid.assert_not_called()
    update_admin.assert_not_awaited()
