from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.crud import create_account, create_wallet, get_total_balance
from lnbits.core.models import Account
from lnbits.core.models.misc import BalanceDelta
from lnbits.core.services.funding_source import (
    check_balance_delta_changed,
    check_server_balance_against_node,
    get_balance_delta,
    switch_to_voidwallet,
)
from lnbits.core.services.payments import update_wallet_balance
from lnbits.settings import Settings


@pytest.mark.anyio
async def test_switch_to_voidwallet_returns_when_already_using_voidwallet(
    settings: Settings, mocker: MockerFixture
):
    original_backend_class = settings.lnbits_backend_wallet_class
    try:
        settings.lnbits_backend_wallet_class = "FakeWallet"
        mocker.patch(
            "lnbits.core.services.funding_source.get_funding_source",
            return_value=type("VoidWallet", (), {})(),
        )
        set_funding_source = mocker.patch(
            "lnbits.core.services.funding_source.set_funding_source"
        )

        await switch_to_voidwallet()

        set_funding_source.assert_not_called()
        assert settings.lnbits_backend_wallet_class == "FakeWallet"
    finally:
        settings.lnbits_backend_wallet_class = original_backend_class


@pytest.mark.anyio
async def test_switch_to_voidwallet_updates_backend_class(
    settings: Settings, mocker: MockerFixture
):
    original_backend_class = settings.lnbits_backend_wallet_class
    try:
        settings.lnbits_backend_wallet_class = "FakeWallet"
        mocker.patch(
            "lnbits.core.services.funding_source.get_funding_source",
            return_value=type("FakeWallet", (), {})(),
        )
        set_funding_source = mocker.patch(
            "lnbits.core.services.funding_source.set_funding_source"
        )

        await switch_to_voidwallet()

        set_funding_source.assert_called_once_with("VoidWallet")
        assert settings.lnbits_backend_wallet_class == "VoidWallet"
    finally:
        settings.lnbits_backend_wallet_class = original_backend_class


@pytest.mark.anyio
async def test_get_balance_delta(mocker: MockerFixture):
    baseline_balance = await get_total_balance()
    await _create_wallet_with_balance(11)
    funding_source = SimpleNamespace(
        status=mocker.AsyncMock(
            return_value=SimpleNamespace(balance_msat=7_000, error_message=None)
        )
    )
    mocker.patch(
        "lnbits.core.services.funding_source.get_funding_source",
        return_value=funding_source,
    )

    delta = await get_balance_delta()
    expected_balance_sats = (baseline_balance + 11_000) // 1000

    assert delta.lnbits_balance_sats == expected_balance_sats
    assert delta.node_balance_sats == 7
    assert delta.delta_sats == expected_balance_sats - 7


@pytest.mark.anyio
async def test_check_server_balance_against_node_notifies_and_switches(
    settings: Settings, mocker: MockerFixture
):
    original_switch = settings.lnbits_watchdog_switch_to_voidwallet
    original_notification = settings.lnbits_notification_watchdog
    original_delta = settings.lnbits_watchdog_delta
    try:
        settings.lnbits_watchdog_switch_to_voidwallet = True
        settings.lnbits_notification_watchdog = True
        settings.lnbits_watchdog_delta = 5
        mocker.patch(
            "lnbits.core.services.funding_source.get_funding_source",
            return_value=type("FakeWallet", (), {})(),
        )
        mocker.patch(
            "lnbits.core.services.funding_source.get_balance_delta",
            mocker.AsyncMock(
                return_value=BalanceDelta(
                    lnbits_balance_sats=12,
                    node_balance_sats=1,
                )
            ),
        )
        enqueue = mocker.patch(
            "lnbits.core.services.funding_source.enqueue_admin_notification"
        )
        switch = mocker.patch(
            "lnbits.core.services.funding_source.switch_to_voidwallet",
            mocker.AsyncMock(),
        )

        await check_server_balance_against_node()

        enqueue.assert_called_once()
        switch.assert_awaited_once()
    finally:
        settings.lnbits_watchdog_switch_to_voidwallet = original_switch
        settings.lnbits_notification_watchdog = original_notification
        settings.lnbits_watchdog_delta = original_delta


@pytest.mark.anyio
async def test_check_balance_delta_changed_tracks_and_notifies(
    settings: Settings, mocker: MockerFixture
):
    settings_any = cast(Any, settings)
    original_latest = settings.latest_balance_delta_sats
    original_threshold = settings.notification_balance_delta_threshold_sats
    try:
        settings_any.latest_balance_delta_sats = None
        settings.notification_balance_delta_threshold_sats = 3
        mocker.patch(
            "lnbits.core.services.funding_source.get_balance_delta",
            mocker.AsyncMock(
                side_effect=[
                    BalanceDelta(lnbits_balance_sats=12, node_balance_sats=10),
                    BalanceDelta(lnbits_balance_sats=20, node_balance_sats=10),
                ]
            ),
        )
        enqueue = mocker.patch(
            "lnbits.core.services.funding_source.enqueue_admin_notification"
        )

        await check_balance_delta_changed()
        enqueue.assert_not_called()
        assert settings.latest_balance_delta_sats == 2

        await check_balance_delta_changed()
        enqueue.assert_called_once()
        assert settings.latest_balance_delta_sats == 10
    finally:
        settings_any.latest_balance_delta_sats = original_latest
        settings.notification_balance_delta_threshold_sats = original_threshold


async def _create_wallet_with_balance(amount: int):
    user_id = uuid4().hex
    await create_account(Account(id=user_id, username=f"user_{user_id[:8]}"))
    wallet = await create_wallet(user_id=user_id, wallet_name="wallet")
    await update_wallet_balance(wallet=wallet, amount=amount)
    return wallet
