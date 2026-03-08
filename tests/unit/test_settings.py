import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.settings import (
    AssetSettings,
    ExchangeRateProvider,
    InstalledExtensionsSettings,
    NotificationsSettings,
    PublicSettings,
    RedirectPath,
    SecuritySettings,
    Settings,
    list_parse_fallback,
    set_cli_settings,
)

lnurlp_redirect_path = {
    "from_path": "/.well-known/lnurlp",
    "redirect_to_path": "/api/v1/well-known",
}
lnurlp_redirect_path_with_headers = {
    "from_path": "/.well-known/lnurlp",
    "redirect_to_path": "/api/v1/well-known",
    "header_filters": {"accept": "application/nostr+json"},
}

lnaddress_redirect_path = {
    "from_path": "/.well-known/lnurlp",
    "redirect_to_path": "/api/v1/well-known",
}

nostrrelay_redirect_path = {
    "from_path": "/",
    "redirect_to_path": "/api/v1/relay-info",
    "header_filters": {"accept": "application/nostr+json"},
}


@pytest.fixture()
def lnurlp():
    return RedirectPath(ext_id="lnurlp", **lnurlp_redirect_path)


@pytest.fixture()
def lnurlp_with_headers():
    return RedirectPath(
        ext_id="lnurlp_with_headers", **lnurlp_redirect_path_with_headers
    )


@pytest.fixture()
def lnaddress():
    return RedirectPath(ext_id="lnaddress", **lnaddress_redirect_path)


@pytest.fixture()
def nostrrelay():
    return RedirectPath(ext_id="nostrrelay", **nostrrelay_redirect_path)


def test_redirect_path_self_not_in_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert not lnurlp.in_conflict(lnurlp), "Path is not in conflict with itself."
    assert not lnaddress.in_conflict(lnaddress), "Path is not in conflict with itself."
    assert not nostrrelay.in_conflict(
        nostrrelay
    ), "Path is not in conflict with itself."

    assert not lnurlp.in_conflict(nostrrelay)

    assert not nostrrelay.in_conflict(lnurlp)


def test_redirect_path_not_in_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):

    assert not lnurlp.in_conflict(nostrrelay)

    assert not nostrrelay.in_conflict(lnurlp)

    assert not lnaddress.in_conflict(nostrrelay)

    assert not nostrrelay.in_conflict(lnaddress)


def test_redirect_path_in_conflict(lnurlp: RedirectPath, lnaddress: RedirectPath):
    assert lnurlp.in_conflict(lnaddress)
    assert lnaddress.in_conflict(lnurlp)


def test_redirect_path_find_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert lnurlp.find_in_conflict([nostrrelay, lnaddress])
    assert lnurlp.find_in_conflict([lnaddress, nostrrelay])
    assert lnaddress.find_in_conflict([nostrrelay, lnurlp])
    assert lnaddress.find_in_conflict([lnurlp, nostrrelay])


def test_redirect_path_find_no_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert not nostrrelay.find_in_conflict([lnurlp, lnaddress])
    assert not lnurlp.find_in_conflict([nostrrelay])
    assert not lnaddress.find_in_conflict([nostrrelay])


def test_redirect_path_in_conflict_with_headers(
    lnurlp: RedirectPath, lnurlp_with_headers: RedirectPath
):
    assert lnurlp.in_conflict(lnurlp_with_headers)
    assert lnurlp_with_headers.in_conflict(lnurlp)


def test_redirect_path_matches_with_headers(
    lnurlp: RedirectPath, lnurlp_with_headers: RedirectPath
):
    headers_list = list(lnurlp_with_headers.header_filters.items())
    assert lnurlp.redirect_matches(
        path=lnurlp_with_headers.from_path,
        req_headers=headers_list,
    )
    assert lnurlp_with_headers.redirect_matches(
        path=lnurlp_redirect_path["from_path"],
        req_headers=[("ACCEPT", "APPlication/nostr+json")],
    )
    assert lnurlp_with_headers.redirect_matches(
        path=lnurlp_redirect_path["from_path"],
        req_headers=[("accept", "application/nostr+json"), ("my_header", "my_value")],
    )

    assert not lnurlp_with_headers.redirect_matches(
        path=lnurlp_redirect_path["from_path"], req_headers=[]
    )
    assert not lnurlp_with_headers.redirect_matches(
        path=lnurlp_redirect_path["from_path"],
        req_headers=[("accept", "application/json")],
    )
    assert not lnurlp_with_headers.redirect_matches(path="/random/path", req_headers=[])
    assert not lnurlp_with_headers.redirect_matches(path="/random_path", req_headers=[])
    assert not lnurlp_with_headers.redirect_matches(
        path="/.well-known/lnurlp", req_headers=[]
    )
    assert lnurlp.redirect_matches(path="/.well-known/lnurlp", req_headers=[])
    assert lnurlp.redirect_matches(
        path="/.well-known/lnurlp/some/other/path", req_headers=[]
    )
    assert lnurlp.redirect_matches(
        path="/.well-known/lnurlp/some/other/path",
        req_headers=headers_list,
    )
    assert not lnurlp_with_headers.redirect_matches(
        path="/.well-known/lnurlp", req_headers=[]
    )
    assert not lnurlp_with_headers.redirect_matches(
        path="/.well-known/lnurlp/some/other/path", req_headers=[]
    )
    assert lnurlp_with_headers.redirect_matches(
        path="/.well-known/lnurlp/some/other/path",
        req_headers=headers_list,
    )


def test_redirect_path_new_path_from(lnurlp: RedirectPath):
    assert lnurlp.new_path_from("") == "/lnurlp/api/v1/well-known"
    assert lnurlp.new_path_from("/") == "/lnurlp/api/v1/well-known"
    assert lnurlp.new_path_from("/path") == "/lnurlp/api/v1/well-known"
    assert lnurlp.new_path_from("/path/more") == "/lnurlp/api/v1/well-known"

    assert lnurlp.new_path_from("/.well-known/lnurlp") == "/lnurlp/api/v1/well-known"
    assert (
        lnurlp.new_path_from("/.well-known/lnurlp/path")
        == "/lnurlp/api/v1/well-known/path"
    )
    assert (
        lnurlp.new_path_from("/.well-known/lnurlp/path/more")
        == "/lnurlp/api/v1/well-known/path/more"
    )


def test_list_parse_fallback():
    assert list_parse_fallback("a, b, c") == ["a", "b", "c"]
    assert list_parse_fallback('["a", "b"]') == ["a", "b"]
    assert list_parse_fallback("") == []


def test_exchange_rate_provider_convert_ticker():
    provider = ExchangeRateProvider(
        name="Provider",
        api_url="https://example.com",
        path="$.price",
        ticker_conversion=["USD:USDT"],
    )
    invalid_provider = ExchangeRateProvider(
        name="Invalid",
        api_url="https://example.com",
        path="$.price",
        ticker_conversion=["invalid"],
    )

    assert provider.convert_ticker("USD") == "USDT"
    assert provider.convert_ticker("EUR") == "EUR"
    assert invalid_provider.convert_ticker("USD") == "USD"


def test_installed_extensions_settings_activate_and_deactivate_paths():
    installed = InstalledExtensionsSettings()
    redirects = [
        {
            "from_path": "/.well-known/lnurlp",
            "redirect_to_path": "/api/v1/well-known",
        }
    ]

    installed.activate_extension_paths(
        "lnurlp",
        upgrade_hash="hash123",
        ext_redirects=redirects,
    )

    redirect = installed.find_extension_redirect("/.well-known/lnurlp", [])
    assert redirect is not None
    assert redirect.ext_id == "lnurlp"
    assert installed.lnbits_upgraded_extensions["lnurlp"] == "hash123"
    assert "lnurlp" in installed.lnbits_installed_extensions_ids

    installed.deactivate_extension_paths("lnurlp")

    assert "lnurlp" in installed.lnbits_deactivated_extensions
    assert installed.find_extension_redirect("/.well-known/lnurlp", []) is None


def test_installed_extensions_settings_detects_conflicting_redirects():
    installed = InstalledExtensionsSettings(
        lnbits_extensions_redirects=[
            RedirectPath(
                ext_id="ext_a",
                from_path="/.well-known/lnurlp",
                redirect_to_path="/api/v1/well-known",
            )
        ]
    )

    with pytest.raises(ValueError, match="Cannot redirect for extension 'ext_b'"):
        installed.activate_extension_paths(
            "ext_b",
            ext_redirects=[
                {
                    "from_path": "/.well-known/lnurlp",
                    "redirect_to_path": "/api/v1/well-known",
                }
            ],
        )


def test_settings_helper_methods(settings: Settings, mocker: MockerFixture):
    mocker.patch.object(settings, "super_user", "super-user")
    mocker.patch.object(settings, "lnbits_admin_users", ["admin-user"])
    mocker.patch.object(settings, "lnbits_allowed_users", ["allowed-user"])
    mocker.patch.object(settings, "lnbits_installed_extensions_ids", {"installed"})
    mocker.patch.object(settings, "lnbits_all_extensions_ids", {"installed", "new"})

    assert settings.is_user_allowed("allowed-user") is True
    assert settings.is_user_allowed("admin-user") is True
    assert settings.is_user_allowed("super-user") is True
    assert settings.is_user_allowed("random-user") is False
    assert settings.is_super_user("super-user") is True
    assert settings.is_admin_user("admin-user") is True
    assert settings.is_installed_extension_id("installed") is True
    assert settings.is_ready_to_install_extension_id("new") is True
    assert settings.is_ready_to_install_extension_id("installed") is False


def test_asset_security_and_notification_helpers(
    settings: Settings, mocker: MockerFixture
):
    mocker.patch.object(settings, "super_user", "super-user")
    mocker.patch.object(settings, "lnbits_admin_users", ["admin-user"])

    asset_settings = AssetSettings(lnbits_assets_no_limit_users=["vip-user"])
    security_settings = SecuritySettings(lnbits_wallet_limit_max_balance=100)
    notification_settings = NotificationsSettings(
        lnbits_nostr_notifications_enabled=True,
        lnbits_nostr_notifications_private_key="nostr-key",
        lnbits_telegram_notifications_enabled=True,
        lnbits_telegram_notifications_access_token="telegram-token",
    )

    assert asset_settings.is_unlimited_assets_user("admin-user") is True
    assert asset_settings.is_unlimited_assets_user("vip-user") is True
    assert asset_settings.is_unlimited_assets_user("random-user") is False
    assert security_settings.is_wallet_max_balance_exceeded(101) is True
    assert security_settings.is_wallet_max_balance_exceeded(100) is False
    assert notification_settings.is_nostr_notifications_configured() is True
    assert notification_settings.is_telegram_notifications_configured() is True


def test_public_settings_from_settings(settings: Settings):
    original_site_title = settings.lnbits_site_title
    original_ad_space = settings.lnbits_ad_space
    original_ad_space_enabled = settings.lnbits_ad_space_enabled
    original_installed_extensions = settings.lnbits_installed_extensions_ids
    original_first_install_token = settings.first_install_token
    try:
        settings.lnbits_site_title = "Test LNbits"
        settings.lnbits_ad_space = "https://example.com;/banner.png;/thumb.png"
        settings.lnbits_ad_space_enabled = True
        settings.lnbits_installed_extensions_ids = {"ext_a"}
        settings.first_install_token = "token"

        public = PublicSettings.from_settings(settings)

        assert public.site_title == "Test LNbits"
        assert public.show_ad_space is True
        assert public.ad_space == [["https://example.com", "/banner.png", "/thumb.png"]]
        assert set(public.extensions) == {"ext_a"}
        assert public.has_first_install_token is True
    finally:
        settings.lnbits_site_title = original_site_title
        settings.lnbits_ad_space = original_ad_space
        settings.lnbits_ad_space_enabled = original_ad_space_enabled
        settings.lnbits_installed_extensions_ids = original_installed_extensions
        settings.first_install_token = original_first_install_token


def test_set_cli_settings_updates_runtime_settings(settings: Settings):
    original_host = settings.host
    try:
        set_cli_settings(host="0.0.0.0")
        assert settings.host == "0.0.0.0"
    finally:
        settings.host = original_host
