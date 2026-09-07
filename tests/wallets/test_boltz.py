import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.settings import SuperUserSettings
from lnbits.wallets import BoltzWallet, get_funding_source, set_funding_source


def test_boltz_disabled_before_connecting(mocker: MockerFixture):
    channel = mocker.patch("lnbits.wallets.boltz.grpc.aio.insecure_channel")
    with pytest.raises(RuntimeError, match="BoltzWallet is temporarily disabled"):
        BoltzWallet()
    channel.assert_not_called()


def test_boltz_selection_rejected_without_replacing_funding_source():
    original = get_funding_source()
    with pytest.raises(RuntimeError, match="BoltzWallet is temporarily disabled"):
        set_funding_source("BoltzWallet")
    assert get_funding_source() is original


def test_boltz_hidden_from_funding_source_choices():
    assert "BoltzWallet" not in SuperUserSettings().lnbits_allowed_funding_sources
    configured = SuperUserSettings(
        lnbits_allowed_funding_sources=["BoltzWallet", "VoidWallet", "BlinkWallet"]
    )
    assert configured.lnbits_allowed_funding_sources == ["VoidWallet", "BlinkWallet"]
