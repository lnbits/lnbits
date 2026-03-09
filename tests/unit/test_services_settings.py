import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import create_admin_settings, delete_admin_settings, get_super_settings
from lnbits.core.crud.settings import get_settings_field
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
    previous_settings = await get_super_settings()
    previous_private = settings.lnbits_webpush_privkey
    previous_public = settings.lnbits_webpush_pubkey
    previous_admin_ui = settings.lnbits_admin_ui
    await delete_admin_settings()

    settings.lnbits_webpush_privkey = ""
    settings.lnbits_webpush_pubkey = None
    settings.lnbits_admin_ui = True
    mocker.patch("lnbits.core.services.settings.Vapid", return_value=FakeVapid())
    mocker.patch("lnbits.core.services.settings.b64urlencode", return_value="public-key")
    try:
        await check_webpush_settings()

        stored_private = await get_settings_field("lnbits_webpush_privkey")
        stored_public = await get_settings_field("lnbits_webpush_pubkey")

        assert settings.lnbits_webpush_privkey == "private-key"
        assert settings.lnbits_webpush_pubkey == "public-key"
        assert stored_private is not None
        assert stored_private.value == "private-key"
        assert stored_public is not None
        assert stored_public.value == "public-key"
    finally:
        await delete_admin_settings()
        if previous_settings:
            await create_admin_settings(
                previous_settings.super_user,
                previous_settings.dict(exclude={"super_user"}),
            )
            update_cached_settings(previous_settings.dict())
        settings.lnbits_webpush_privkey = previous_private
        settings.lnbits_webpush_pubkey = previous_public
        settings.lnbits_admin_ui = previous_admin_ui


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
    previous_private = settings.lnbits_webpush_privkey
    previous_public = settings.lnbits_webpush_pubkey
    previous_private_field = await get_settings_field("lnbits_webpush_privkey")
    previous_public_field = await get_settings_field("lnbits_webpush_pubkey")
    settings.lnbits_webpush_privkey = "existing-private-key"
    settings.lnbits_webpush_pubkey = "existing-public-key"
    vapid = mocker.patch("lnbits.core.services.settings.Vapid")
    try:
        await check_webpush_settings()
    finally:
        settings.lnbits_webpush_privkey = previous_private
        settings.lnbits_webpush_pubkey = previous_public

    assert await get_settings_field("lnbits_webpush_privkey") == previous_private_field
    assert await get_settings_field("lnbits_webpush_pubkey") == previous_public_field
    vapid.assert_not_called()
