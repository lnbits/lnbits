import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.settings import Settings, SuperUserSettings
from lnbits.wallets import get_funding_source, set_funding_source


@pytest.mark.parametrize("wallet_class", ["BoltzWallet", "BlinkWallet"])
def test_blocked_source_rejected_before_constructing(
    mocker: MockerFixture, settings: Settings, wallet_class: str
):
    mocker.patch.object(settings, "lnbits_blocked_funding_sources", [wallet_class])
    constructor = mocker.patch(f"lnbits.wallets.{wallet_class}")
    original = get_funding_source()
    with pytest.raises(
        RuntimeError, match="disabled by LNBITS_BLOCKED_FUNDING_SOURCES"
    ):
        set_funding_source(wallet_class)
    constructor.assert_not_called()
    assert get_funding_source() is original


def test_boltz_can_be_reenabled(mocker: MockerFixture, settings: Settings):
    mocker.patch.object(settings, "lnbits_blocked_funding_sources", [])
    mocker.patch.object(settings, "lnbits_backend_wallet_class", "BoltzWallet")
    mocker.patch("lnbits.wallets.funding_source", get_funding_source())
    mocker.patch.object(settings, "has_nodemanager", settings.has_nodemanager)
    mocker.patch.object(settings, "has_holdinvoice", settings.has_holdinvoice)
    constructor = mocker.patch("lnbits.wallets.BoltzWallet")
    constructor.return_value.has_feature.return_value = False
    set_funding_source()
    constructor.assert_called_once_with()
    assert get_funding_source() is constructor.return_value


def test_boltz_blocked_by_default_without_hiding_saved_settings():
    configured = SuperUserSettings()
    assert configured.lnbits_blocked_funding_sources == ["BoltzWallet"]
    assert "BoltzWallet" in configured.lnbits_allowed_funding_sources


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("[]", []),
        ('["BoltzWallet"]', ["BoltzWallet"]),
        ("BoltzWallet,BlinkWallet", ["BoltzWallet", "BlinkWallet"]),
    ],
)
def test_blocked_sources_from_environment(monkeypatch, value, expected):
    monkeypatch.setenv("LNBITS_BLOCKED_FUNDING_SOURCES", value)
    assert Settings().lnbits_blocked_funding_sources == expected
