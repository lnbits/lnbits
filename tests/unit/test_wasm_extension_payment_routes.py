import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from lnbits.core.views.extension_api import (
    _wasm_payment_intent_wallet,
    api_retry_failed_wasm_payment_intent,
)
from lnbits.core.wasm_ext.api.models import ManualPaymentIntentRetryRequest
from lnbits.helpers import sha256s


@pytest.mark.anyio
@pytest.mark.parametrize(
    "account_id,is_admin,wallet_user,allowed",
    [
        ("owner", False, "owner", True),
        ("other", False, "owner", False),
        ("admin", True, "owner", True),
    ],
)
async def test_manual_payment_intent_access_is_wallet_owner_or_admin_only(
    mocker, account_id, is_admin, wallet_user, allowed
):
    wallet = SimpleNamespace(user=wallet_user)
    mocker.patch(
        "lnbits.core.views.extension_api.get_installed_extension",
        AsyncMock(return_value=SimpleNamespace(is_wasm=True)),
    )
    mocker.patch(
        "lnbits.core.views.extension_api.get_wallet",
        AsyncMock(return_value=wallet),
    )

    if allowed:
        assert (
            await _wasm_payment_intent_wallet(
                "demoext",
                "wallet-1",
                cast(Any, SimpleNamespace(id=account_id, is_admin=is_admin)),
            )
            is wallet
        )
    else:
        with pytest.raises(HTTPException) as error:
            await _wasm_payment_intent_wallet(
                "demoext",
                "wallet-1",
                cast(Any, SimpleNamespace(id=account_id, is_admin=is_admin)),
            )
        assert error.value.status_code == 403


@pytest.mark.anyio
async def test_failed_payment_intent_retry_grants_host_permission(mocker):
    wallet = SimpleNamespace(user="owner")
    mocker.patch(
        "lnbits.core.views.extension_api._wasm_payment_intent_wallet",
        AsyncMock(return_value=wallet),
    )
    mocker.patch(
        "lnbits.core.views.extension_api.get_payment_intent_by_id",
        AsyncMock(
            return_value={
                "status": "failed",
                "request_json": json.dumps(
                    {
                        "destination": "user@example.com",
                        "amount_msat": 1000,
                        "max_fee_msat": 100,
                        "description": None,
                    }
                ),
                "idempotency_key": "retry-1",
                "max_fee_msat": 100,
            }
        ),
    )
    mocker.patch(
        "lnbits.core.views.extension_api.record_payment_intent_operator_action",
        AsyncMock(),
    )
    create_or_get = AsyncMock(
        return_value=SimpleNamespace(
            status="processing", dict=lambda: {"status": "processing"}
        )
    )
    host = mocker.patch(
        "lnbits.core.views.extension_api.ExtensionHostAPI",
        return_value=SimpleNamespace(wallet_payment_intent_create_or_get=create_or_get),
    )

    response = await api_retry_failed_wasm_payment_intent(
        "demoext",
        "intent-1",
        ManualPaymentIntentRetryRequest(wallet_id="wallet-1", note="Retry"),
        cast(Any, SimpleNamespace(id="owner", is_admin=False)),
    )

    assert response == {"status": "processing"}
    host.assert_called_once_with(
        "demoext",
        ["wallet.payment_intents"],
        user_id="owner",
        owner_id=sha256s("owner"),
    )
    retry_call = create_or_get.await_args
    assert retry_call is not None
    assert retry_call.args[0].retry_failed is True
