from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException
from pytest_mock.plugin import MockerFixture

from lnbits.core.services.payments import _resolve_fee_limit_msat
from lnbits.settings import Settings


def _funding_source_mock(supports: bool) -> MagicMock:
    fs = MagicMock()
    fs.supports_fee_limit_msat = supports
    return fs


@pytest.mark.anyio
async def test_resolve_fee_limit_none_returns_operator_cap(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_reserve_fee_percent = 1
    settings.lnbits_reserve_fee_min = 0
    get_fs = mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=_funding_source_mock(supports=False),
    )

    effective = _resolve_fee_limit_msat(
        amount_msat=1_000_000, caller_fee_limit_msat=None
    )

    # 1% of 1_000_000 msat = 10_000 msat; caller passed nothing so we fall back
    # to the operator cap unconditionally and never consult the funding source.
    assert effective == 10_000
    assert get_fs.call_count == 0


@pytest.mark.anyio
async def test_resolve_fee_limit_caller_below_operator(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_reserve_fee_percent = 1
    settings.lnbits_reserve_fee_min = 0
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=_funding_source_mock(supports=True),
    )

    effective = _resolve_fee_limit_msat(
        amount_msat=1_000_000, caller_fee_limit_msat=2_500
    )

    # operator allows 10_000 msat, caller asks 2_500 → caller wins (stricter).
    assert effective == 2_500


@pytest.mark.anyio
async def test_resolve_fee_limit_caller_above_operator(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_reserve_fee_percent = 1
    settings.lnbits_reserve_fee_min = 0
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=_funding_source_mock(supports=True),
    )

    effective = _resolve_fee_limit_msat(
        amount_msat=1_000_000, caller_fee_limit_msat=50_000
    )

    # caller can never raise the operator's ceiling.
    assert effective == 10_000


@pytest.mark.anyio
async def test_resolve_fee_limit_unsupported_backend_raises(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_reserve_fee_percent = 1
    settings.lnbits_reserve_fee_min = 0
    mocker.patch(
        "lnbits.core.services.payments.get_funding_source",
        return_value=_funding_source_mock(supports=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        _resolve_fee_limit_msat(amount_msat=1_000_000, caller_fee_limit_msat=2_500)

    assert exc_info.value.status_code == 400
    assert "fee_limit_msat" in exc_info.value.detail


@pytest.mark.anyio
async def test_lnbits_driver_propagates_fee_limit_msat_in_payload(
    settings: Settings, mocker: MockerFixture
):
    settings.lnbits_endpoint = "https://example.invalid"
    settings.lnbits_admin_key = "deadbeef"
    settings.lnbits_invoice_key = "deadbeef"
    settings.lnbits_key = "deadbeef"

    from lnbits.wallets.lnbits import LNbitsWallet

    # The capability flag is declared at the class — not env — so that
    # operators cannot opt a non-propagating driver into the feature.
    assert LNbitsWallet.supports_fee_limit_msat is True

    wallet = LNbitsWallet()

    # Capture the JSON payload sent by the driver without doing real I/O.
    captured: dict = {}

    async def fake_post(url, json, timeout=None):
        captured["url"] = url
        captured["json"] = json
        del timeout
        response = MagicMock(spec=httpx.Response)
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value={"payment_hash": "ph"})
        return response

    mocker.patch.object(wallet.client, "post", side_effect=fake_post)
    mocker.patch.object(
        wallet,
        "get_payment_status",
        AsyncMock(
            return_value=MagicMock(success=True, fee_msat=0, preimage="00", paid=True)
        ),
    )

    # With a cap → field present.
    await wallet.pay_invoice(bolt11="lnbcdummy", fee_limit_msat=1234)
    assert captured["json"]["fee_limit_msat"] == 1234
    assert captured["json"]["out"] is True
    assert captured["json"]["bolt11"] == "lnbcdummy"

    # Without a cap (legacy callers) → field absent.
    captured.clear()
    await wallet.pay_invoice(bolt11="lnbcdummy", fee_limit_msat=None)
    assert "fee_limit_msat" not in captured["json"]


@pytest.mark.anyio
async def test_custodial_drivers_keep_default_supports_flag():
    # The flag defaults to False; only the audited propagating drivers may
    # flip it. Catching a regression here is cheaper than reading every diff.
    from lnbits.wallets.alby import AlbyWallet
    from lnbits.wallets.blink import BlinkWallet
    from lnbits.wallets.boltz import BoltzWallet
    from lnbits.wallets.cliche import ClicheWallet
    from lnbits.wallets.eclair import EclairWallet
    from lnbits.wallets.lnpay import LNPayWallet
    from lnbits.wallets.lntips import LnTipsWallet
    from lnbits.wallets.nwc import NWCWallet
    from lnbits.wallets.opennode import OpenNodeWallet
    from lnbits.wallets.phoenixd import PhoenixdWallet
    from lnbits.wallets.strike import StrikeWallet
    from lnbits.wallets.zbd import ZBDWallet

    for cls in (
        AlbyWallet,
        BlinkWallet,
        BoltzWallet,
        ClicheWallet,
        EclairWallet,
        LNPayWallet,
        LnTipsWallet,
        NWCWallet,
        OpenNodeWallet,
        PhoenixdWallet,
        StrikeWallet,
        ZBDWallet,
    ):
        assert cls.supports_fee_limit_msat is False, cls.__name__
