import hashlib
from json import JSONDecodeError
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import shortuuid
from pytest_mock.plugin import MockerFixture

from lnbits import bolt11
from lnbits.core.models import CreateInvoice, Payment
from lnbits.core.models.users import Account, UserExtra, UserLabel
from lnbits.core.services.users import create_user_account
from lnbits.core.views.payment_api import api_payment
from lnbits.fiat.base import FiatInvoiceResponse
from lnbits.settings import Settings

from ..helpers import (
    get_random_invoice_data,
    get_random_string,
)


# create account POST /api/v1/account
@pytest.mark.anyio
async def test_create_account(client, settings: Settings):
    settings.lnbits_allow_new_accounts = False
    response = await client.post("/api/v1/account", json={"name": "test"})

    assert response.status_code == 400
    assert response.json().get("detail") == "Account creation is disabled."

    settings.lnbits_allow_new_accounts = True
    response = await client.post("/api/v1/account", json={"name": "test"})
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    assert result["name"] == "test"
    assert "balance_msat" in result
    assert "id" in result
    assert "user" in result


# check POST and DELETE /api/v1/wallet with adminkey and user token:
# create additional wallet and delete it
@pytest.mark.anyio
async def test_create_wallet_and_delete(
    client, adminkey_headers_from, user_headers_from
):
    response = await client.post(
        "/api/v1/wallet", json={"name": "test"}, headers=adminkey_headers_from
    )
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    assert result["name"] == "test"
    assert "balance_msat" in result
    assert "id" in result
    assert "adminkey" in result

    invalid_response = await client.delete(
        f"/api/v1/wallet/{result['id']}",
        headers={
            "X-Api-Key": result["adminkey"],
            "Content-type": "application/json",
        },
    )
    assert invalid_response.status_code == 401

    response = await client.delete(
        f"/api/v1/wallet/{result['id']}",
        headers=user_headers_from,
    )
    assert response.status_code == 200

    # get deleted wallet
    response = await client.get(
        "/api/v1/wallet",
        headers={
            "X-Api-Key": result["adminkey"],
            "Content-type": "application/json",
        },
    )
    assert response.status_code == 404


# check GET /api/v1/wallet with inkey: wallet info, no balance
@pytest.mark.anyio
async def test_get_wallet_inkey(client, inkey_headers_to):
    response = await client.get("/api/v1/wallet", headers=inkey_headers_to)
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    assert "balance" in result
    assert "id" not in result


# check GET /api/v1/wallet with adminkey: wallet info with balance
@pytest.mark.anyio
async def test_get_wallet_adminkey(client, adminkey_headers_to):
    response = await client.get("/api/v1/wallet", headers=adminkey_headers_to)
    assert response.status_code == 200
    result = response.json()
    assert "name" in result
    assert "balance" in result
    assert "id" in result


# check PUT /api/v1/wallet/newwallet: empty request where admin key is needed
@pytest.mark.anyio
async def test_put_empty_request_expected_admin_keys(client):
    response = await client.put("/api/v1/wallet/newwallet")
    assert response.status_code == 401


# check POST /api/v1/payments: empty request where invoice key is needed
@pytest.mark.anyio
async def test_post_empty_request_expected_invoice_keys(client):
    response = await client.post("/api/v1/payments")
    assert response.status_code == 401


# check POST /api/v1/payments: invoice creation
@pytest.mark.anyio
async def test_create_invoice(client, inkey_headers_to):
    data = await get_random_invoice_data()
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    assert response.status_code == 201
    invoice = response.json()
    assert "payment_hash" in invoice
    assert len(invoice["payment_hash"]) == 64
    assert "bolt11" in invoice
    assert "checking_id" in invoice
    assert len(invoice["checking_id"])
    return invoice


@pytest.mark.anyio
async def test_create_invoice_fiat_amount(client, inkey_headers_to):
    data = await get_random_invoice_data()
    data["unit"] = "EUR"
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    assert response.status_code == 201
    invoice = response.json()
    decode = bolt11.decode(invoice["bolt11"])
    assert decode.amount_msat != data["amount"] * 1000
    assert decode.payment_hash

    response = await client.get(
        f"/api/v1/payments/{decode.payment_hash}", headers=inkey_headers_to
    )
    assert response.is_success
    res_data = response.json()
    extra = res_data["details"]["extra"]
    assert extra["fiat_amount"] == data["amount"]
    assert extra["fiat_currency"] == data["unit"]
    assert extra["fiat_rate"]


@pytest.mark.anyio
async def test_create_fiat_invoice(
    client, inkey_headers_to, settings: Settings, mocker: MockerFixture
):
    data = await get_random_invoice_data()
    data["unit"] = "EUR"
    data["fiat_provider"] = "stripe"

    settings.stripe_enabled = True
    settings.stripe_api_secret_key = "mock_sk_test_4eC39HqLyjWDarjtT1zdp7dc"

    fiat_payment_request = "https://stripe.com/pay/session_123"
    fiat_mock_response = FiatInvoiceResponse(
        ok=True,
        checking_id=f"session_123_{get_random_string(10)}",
        payment_request=fiat_payment_request,
    )

    mocker.patch(
        "lnbits.fiat.StripeWallet.create_invoice",
        AsyncMock(return_value=fiat_mock_response),
    )
    mocker.patch(
        "lnbits.utils.exchange_rates.get_fiat_rate_satoshis",
        AsyncMock(return_value=1000),  # 1 BTC = 100 000 EUR, so 1 EUR = 1000 sats
    )
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    assert response.status_code == 201
    invoice = response.json()
    decode = bolt11.decode(invoice["bolt11"])
    assert decode.amount_msat == 10_000_000
    assert decode.payment_hash
    assert invoice["fiat_provider"] == "stripe"
    assert invoice["status"] == "pending"
    assert invoice["extra"]["fiat_checking_id"]
    assert invoice["extra"]["fiat_payment_request"] == fiat_payment_request

    response = await client.get(
        f"/api/v1/payments/{decode.payment_hash}", headers=inkey_headers_to
    )
    assert response.is_success
    data = response.json()
    assert data["status"] == "pending"
    invoice = data["details"]

    assert invoice["fiat_provider"] == "stripe"
    assert invoice["status"] == "pending"
    assert invoice["amount"] == 10_000_000
    assert invoice["extra"]["fiat_checking_id"]
    assert invoice["extra"]["fiat_payment_request"] == fiat_payment_request


@pytest.mark.anyio
@pytest.mark.parametrize("currency", ("msat", "RRR"))
async def test_create_invoice_validates_used_currency(
    currency, client, inkey_headers_to
):
    data = await get_random_invoice_data()
    data["unit"] = currency
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    assert response.status_code == 400
    res_data = response.json()
    assert "The provided unit is not supported" in res_data["detail"]


# check POST /api/v1/payments: invoice creation for internal payments only
@pytest.mark.anyio
async def test_create_internal_invoice(client, inkey_headers_to):
    data = await get_random_invoice_data()
    data["internal"] = True
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    invoice = response.json()
    assert response.status_code == 201
    assert "payment_hash" in invoice
    assert len(invoice["payment_hash"]) == 64
    assert "bolt11" in invoice
    assert "checking_id" in invoice
    assert len(invoice["checking_id"])
    return invoice


# check POST /api/v1/payments: invoice with custom expiry
@pytest.mark.anyio
async def test_create_invoice_custom_expiry(client, inkey_headers_to):
    data = await get_random_invoice_data()
    expiry_seconds = 600 * 6 * 24 * 31  # 31 days in the future
    data["expiry"] = expiry_seconds
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    assert response.status_code == 201
    invoice = response.json()
    bolt11_invoice = bolt11.decode(invoice["bolt11"])
    assert bolt11_invoice.expiry == expiry_seconds


# check POST /api/v1/payments: make payment
@pytest.mark.anyio
async def test_pay_invoice(
    client, from_wallet_ws, invoice: Payment, adminkey_headers_from
):
    data = {"out": True, "bolt11": invoice.bolt11}
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code < 300
    invoice_ = response.json()
    assert len(invoice_["payment_hash"]) == 64
    assert len(invoice_["checking_id"]) > 0

    ws_data = from_wallet_ws.receive_json()
    assert "wallet_balance" in ws_data
    payment = Payment(**ws_data["payment"])
    assert payment.payment_hash == invoice_["payment_hash"]

    # websocket from to_wallet cant be tested before https://github.com/lnbits/lnbits/pull/1793
    # data = to_wallet_ws.receive_json()
    # assert "wallet_balance" in data
    # payment = Payment(**data["payment"])
    # assert payment.payment_hash == invoice["payment_hash"]


# check GET /api/v1/payments/<hash>: payment status
@pytest.mark.anyio
async def test_check_payment_without_key(client, invoice: Payment):
    # check the payment status
    response = await client.get(f"/api/v1/payments/{invoice.payment_hash}")
    assert response.status_code < 300
    assert response.json()["paid"] is True
    assert invoice
    # not key, that's why no "details"
    assert "details" not in response.json()


# check GET /api/v1/payments/<hash>: payment status
# NOTE: this test is sensitive to which db is used.
# If postgres: it will succeed only with inkey_headers_from
# If sqlite: it will succeed only with adminkey_headers_to
# TODO: fix this
@pytest.mark.anyio
async def test_check_payment_with_key(client, invoice: Payment, inkey_headers_from):
    # check the payment status
    response = await client.get(
        f"/api/v1/payments/{invoice.payment_hash}", headers=inkey_headers_from
    )
    assert response.status_code < 300
    assert response.json()["paid"] is True
    assert invoice
    # with key, that's why with "details"
    assert "details" in response.json()


# check POST /api/v1/payments: payment with wrong key type
@pytest.mark.anyio
async def test_pay_invoice_wrong_key(client, invoice, adminkey_headers_from):
    data = {"out": True, "bolt11": invoice.bolt11}
    # try payment with wrong key
    wrong_adminkey_headers = adminkey_headers_from.copy()
    wrong_adminkey_headers["X-Api-Key"] = "wrong_key"
    response = await client.post(
        "/api/v1/payments", json=data, headers=wrong_adminkey_headers
    )
    assert response.status_code >= 300  # should fail


# check POST /api/v1/payments: payment with self payment
@pytest.mark.anyio
async def test_pay_invoice_self_payment(client, adminkey_headers_from):
    create_invoice = CreateInvoice(out=False, amount=1000, memo="test")
    response = await client.post(
        "/api/v1/payments",
        json=create_invoice.dict(),
        headers=adminkey_headers_from,
    )
    assert response.status_code < 300
    json_data = response.json()
    data = {"out": True, "bolt11": json_data["bolt11"]}
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code < 300


# check POST /api/v1/payments: payment with invoice key [should fail]
@pytest.mark.anyio
async def test_pay_invoice_invoicekey(client, invoice, inkey_headers_from):
    data = {"out": True, "bolt11": invoice.bolt11}
    # try payment with invoice key
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_from
    )
    assert response.status_code >= 300  # should fail


# check POST /api/v1/payments: payment with admin key, trying to pay twice [should fail]
@pytest.mark.anyio
async def test_pay_invoice_adminkey(client, invoice, adminkey_headers_from):
    data = {"out": True, "bolt11": invoice.bolt11}
    # try payment with admin key
    response = await client.post(
        "/api/v1/payments", json=data, headers=adminkey_headers_from
    )
    assert response.status_code > 300  # should fail


@pytest.mark.anyio
async def test_get_payments(client, inkey_fresh_headers_to, fake_payments):
    _, filters = fake_payments

    async def get_payments(params: dict):
        response = await client.get(
            "/api/v1/payments",
            params=filters | params,
            headers=inkey_fresh_headers_to,
        )
        assert response.status_code == 200
        return [Payment(**payment) for payment in response.json()]

    payments = await get_payments({"sortby": "amount", "direction": "desc", "limit": 2})
    assert len(payments) != 0
    assert payments[-1].amount < payments[0].amount
    assert len(payments) == 2

    payments = await get_payments({"offset": 2, "limit": 2})
    assert len(payments) == 1

    payments = await get_payments({"sortby": "amount", "direction": "asc"})
    assert payments[-1].amount > payments[0].amount

    payments = await get_payments({"search": "xxx"})
    assert len(payments) == 1

    payments = await get_payments({"search": "xx"})
    assert len(payments) == 2

    # amount is in msat
    payments = await get_payments({"amount[gt]": 10000})
    assert len(payments) == 2


@pytest.mark.anyio
async def test_get_payments_paginated(client, inkey_fresh_headers_to, fake_payments):
    fake_data, filters = fake_payments

    response = await client.get(
        "/api/v1/payments/paginated",
        params=filters | {"limit": 2},
        headers=inkey_fresh_headers_to,
    )
    assert response.status_code == 200
    paginated = response.json()
    data = paginated["data"]
    assert len(data) == 2
    assert paginated["total"] == len(fake_data)

    checking_id_list = [payment["checking_id"] for payment in data]
    params = {"checking_id[in]": ",".join(checking_id_list)}
    response = await client.get(
        "/api/v1/payments/paginated",
        params=params,
        headers=inkey_fresh_headers_to,
    )
    data = response.json()["data"]
    assert len(data) == 2
    for payment in data:
        assert payment["checking_id"] in checking_id_list


@pytest.mark.anyio
async def test_get_payments_history(client, inkey_fresh_headers_to, fake_payments):
    fake_data, filters = fake_payments

    response = await client.get(
        "/api/v1/payments/history",
        params=filters,
        headers=inkey_fresh_headers_to,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["income"] == sum(
        [int(payment.amount * 1000) for payment in fake_data if not payment.out]
    )
    assert data[0]["spending"] == sum(
        [int(payment.amount * 1000) for payment in fake_data if payment.out]
    )

    response = await client.get(
        "/api/v1/payments/history?group=INVALID",
        params=filters,
        headers=inkey_fresh_headers_to,
    )

    assert response.status_code == 400


# check POST /api/v1/payments/decode
@pytest.mark.anyio
async def test_decode_invoice(client, invoice: Payment):
    data = {"data": invoice.bolt11}
    response = await client.post(
        "/api/v1/payments/decode",
        json=data,
    )
    assert response.status_code < 300
    assert response.json()["payment_hash"] == invoice.payment_hash


# check api_payment() internal function call (NOT API): payment status
@pytest.mark.anyio
async def test_api_payment_without_key(invoice: Payment):
    # check the payment status
    response = await api_payment(invoice.payment_hash)
    assert isinstance(response, dict)
    assert response["paid"] is True
    # no key, that's why no "details"
    assert "details" not in response


# check api_payment() internal function call (NOT API): payment status
@pytest.mark.anyio
async def test_api_payment_with_key(invoice: Payment, inkey_headers_from):
    # check the payment status
    response = await api_payment(invoice.payment_hash, inkey_headers_from["X-Api-Key"])
    assert isinstance(response, dict)
    assert response["paid"] is True
    assert "details" in response


# check POST /api/v1/payments: invoice creation with a description hash
@pytest.mark.anyio
async def test_create_invoice_with_description_hash(client, inkey_headers_to):
    data = await get_random_invoice_data()
    description = "asdasdasd"
    descr_hash = hashlib.sha256(description.encode()).hexdigest()
    data["description_hash"] = descr_hash
    data["unhashed_description"] = description.encode().hex()
    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    invoice = response.json()

    invoice_bolt11 = bolt11.decode(invoice["bolt11"])
    assert invoice_bolt11.description_hash == descr_hash
    return invoice


@pytest.mark.anyio
async def test_create_invoice_with_unhashed_description(client, inkey_headers_to):
    data = await get_random_invoice_data()
    description = "test description"
    descr_hash = hashlib.sha256(description.encode()).hexdigest()
    data["unhashed_description"] = description.encode().hex()

    response = await client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_to
    )
    invoice = response.json()

    invoice_bolt11 = bolt11.decode(invoice["bolt11"])
    assert invoice_bolt11.description_hash == descr_hash
    assert invoice_bolt11.description is None
    return invoice


@pytest.mark.anyio
async def test_update_wallet(client, adminkey_headers_from):
    name = "new name"
    currency = "EUR"

    response = await client.patch(
        "/api/v1/wallet", json={"name": name}, headers=adminkey_headers_from
    )
    assert response.status_code == 200
    assert response.json()["name"] == name

    response = await client.patch(
        "/api/v1/wallet", json={"currency": currency}, headers=adminkey_headers_from
    )
    assert response.status_code == 200
    assert response.json()["currency"] == currency
    # name is not changed because updates are partial
    assert response.json()["name"] == name


@pytest.mark.anyio
async def test_fiat_tracking(client, adminkey_headers_from, settings: Settings):
    async def create_invoice():
        data = await get_random_invoice_data()
        response = await client.post(
            "/api/v1/payments", json=data, headers=adminkey_headers_from
        )
        assert response.is_success

        response = await client.get(
            f"/api/v1/payments/{response.json()['payment_hash']}",
            headers=adminkey_headers_from,
        )
        assert response.is_success
        return response.json()["details"]

    async def update_currency(currency):
        response = await client.patch(
            "/api/v1/wallet", json={"currency": currency}, headers=adminkey_headers_from
        )
        assert response.is_success
        assert response.json()["currency"] == currency

    await update_currency("")

    settings.lnbits_default_accounting_currency = "USD"
    payment = await create_invoice()
    extra = payment["extra"]
    assert extra["wallet_fiat_currency"] == "USD"
    assert extra["wallet_fiat_amount"] != payment["amount"]
    assert extra["wallet_fiat_rate"]

    await update_currency("EUR")

    payment = await create_invoice()
    extra = payment["extra"]
    assert extra["wallet_fiat_currency"] == "EUR"
    assert extra["wallet_fiat_amount"] != payment["amount"]
    assert extra["wallet_fiat_rate"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "lnurl_response_data, callback_response_data, expected_response",
    [
        # Happy path
        (
            {
                "tag": "withdrawRequest",
                "callback": "https://example.com/callback",
                "k1": "randomk1value",
                "minWithdrawable": 1000,
                "maxWithdrawable": 1_500_000,
            },
            {"status": "OK"},
            {"success": True, "message": "Payment sent with NFC."},
        ),
        # Error loading LNURL request
        (
            "error_loading_lnurl",
            None,
            {
                "detail": "Error loading callback request",
            },
        ),
        # LNURL response with error status
        (
            {
                "status": "ERROR",
                "reason": "Invalid LNURL-withdraw response.",
            },
            None,
            {
                "detail": "Invalid LNURL-withdraw response.",
            },
        ),
        # Invalid LNURL-withdraw pay request
        (
            {
                "tag": "payRequest",
                "callback": "https://example.com/callback",
                "minSendable": 1000,
                "maxSendable": 1_500_000,
                "metadata": '[["text/plain", "Payment to yo"]]',
            },
            None,
            {
                "detail": "Invalid LNURL-withdraw response.",
            },
        ),
        # Error loading callback request
        (
            {
                "tag": "withdrawRequest",
                "callback": "https://example.com/callback",
                "k1": "randomk1value",
                "minWithdrawable": 1000,
                "maxWithdrawable": 1_500_000,
            },
            "error_loading_callback",
            {
                "detail": "Error loading callback request",
            },
        ),
        # Callback response with error status
        (
            {
                "tag": "withdrawRequest",
                "callback": "https://example.com/callback",
                "k1": "randomk1value",
                "minWithdrawable": 1000,
                "maxWithdrawable": 1_500_000,
            },
            {
                "status": "ERROR",
                "reason": "Callback failed",
            },
            {
                "detail": "Callback failed",
            },
        ),
        # Unexpected exception during LNURL response JSON parsing
        (
            "exception_in_lnurl_response_json",
            None,
            {
                "detail": "Invalid JSON response from https://example.com/lnurl",
            },
        ),
    ],
)
async def test_api_payment_pay_with_nfc(
    client,
    mocker: MockerFixture,
    lnurl_response_data,
    callback_response_data,
    expected_response,
):
    payment_request = (
        "lnbc15u1p3xnhl2pp5jptserfk3zk4qy42tlucycrfwxhydvlemu9pqr93tuzlv9cc7g3sdq"
        "svfhkcap3xyhx7un8cqzpgxqzjcsp5f8c52y2stc300gl6s4xswtjpc37hrnnr3c9wvtgjfu"
        "vqmpm35evq9qyyssqy4lgd8tj637qcjp05rdpxxykjenthxftej7a2zzmwrmrl70fyj9hvj0"
        "rewhzj7jfyuwkwcg9g2jpwtk3wkjtwnkdks84hsnu8xps5vsq4gj5hs"
    )
    lnurl = "lnurlw://example.com/lnurl"

    # Create a mock for httpx.AsyncClient
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_async_client

    # Mock the get method
    async def mock_get(url, *_, **__):
        if url == "https://example.com/lnurl":
            if lnurl_response_data == "error_loading_lnurl":
                response = Mock()
                response.is_error = True
                response.status_code = 500
                response.raise_for_status.side_effect = Exception(
                    "Error loading callback request"
                )
                return response
            elif lnurl_response_data == "exception_in_lnurl_response_json":
                response = Mock()
                response.is_error = False
                response.json.side_effect = JSONDecodeError(
                    doc="Simulated exception", pos=0, msg="JSONDecodeError"
                )
                return response
            elif isinstance(lnurl_response_data, dict):
                response = Mock()
                response.is_error = False
                response.json.return_value = lnurl_response_data
                return response
            else:
                # Handle unexpected data
                response = Mock()
                response.is_error = True
                response.status_code = 500
                response.raise_for_status.side_effect = Exception(
                    "Error loading callback request"
                )
                return response
        elif url == "https://example.com/callback":
            if callback_response_data == "error_loading_callback":
                response = Mock()
                response.is_error = True
                response.status_code = 500
                response.raise_for_status.side_effect = Exception(
                    "Error loading callback request"
                )
                return response
            elif isinstance(callback_response_data, dict):
                response = Mock()
                response.is_error = False
                response.json.return_value = callback_response_data
                return response
            else:
                # Handle cases where callback is not called
                response = Mock()
                response.is_error = True
                response.raise_for_status.side_effect = Exception(
                    "Error loading callback request"
                )
                return response
        else:
            response = Mock()
            response.is_error = True
            response.raise_for_status.side_effect = Exception(
                "Error loading callback request"
            )
            return response

    mock_async_client.get.side_effect = mock_get

    # Mock httpx.AsyncClient to return our mock_async_client
    mocker.patch("httpx.AsyncClient", return_value=mock_async_client)

    response = await client.post(
        f"/api/v1/payments/{payment_request}/pay-with-nfc",
        json={"lnurl_w": lnurl},
    )

    assert response.json() == expected_response


@pytest.mark.anyio
async def test_api_payments_pay_lnurl(client, adminkey_headers_from):
    lnurl_data = {
        "res": {
            "callback": "https://xxxxxxx.lnbits.com",
            "minSendable": 1000,
            "maxSendable": 1_500_000,
            "metadata": '[["text/plain", "Payment to yo"]]',
        },
        "amount": 1000,
        "unit": "sat",
        "comment": "test comment",
        "description": "test description",
    }

    # Test with valid callback URL
    response = await client.post(
        "/api/v1/payments/lnurl", json=lnurl_data, headers=adminkey_headers_from
    )
    assert response.status_code == 400

    # Test with invalid callback URL
    lnurl_data["res"]["callback"] = "invalid-url.lnbits.com"
    response = await client.post(
        "/api/v1/payments/lnurl", json=lnurl_data, headers=adminkey_headers_from
    )
    assert response.status_code == 400
    assert "value_error.url.scheme" in response.json()["detail"]


################################ Labels ################################
@pytest.mark.anyio
async def test_api_search_payment_labels(client):
    tiny_id = shortuuid.uuid()[:8]
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"u{tiny_id}",
            extra=UserExtra(
                labels=[
                    UserLabel(name="label A", color="#FF0000"),
                    UserLabel(name="label B", color="#00FF00"),
                ]
            ),
        )
    )
    assert len(user.extra.labels) == 2
    adminkey = user.wallets[0].adminkey
    payments_headers = {
        "X-Api-Key": adminkey,
        "Content-type": "application/json",
    }

    payment_count = 10
    await _create_some_payments(payment_count, client, payments_headers)

    # search payments by label A
    response = await client.get(
        "/api/v1/payments/paginated",
        params={"labels[every]": ["label A"]},
        headers=payments_headers,
    )
    assert response.is_success
    data = response.json()
    assert data["total"] == payment_count // 2
    for payment in data["data"]:
        assert "label A" in payment["labels"]

    # search payments by label B
    response = await client.get(
        "/api/v1/payments/paginated",
        params={"labels[every]": ["label B"]},
        headers=payments_headers,
    )
    assert response.is_success
    data = response.json()
    assert data["total"] == payment_count // 3
    for payment in data["data"]:
        assert "label B" in payment["labels"]

    # search payments by label C
    response = await client.get(
        "/api/v1/payments/paginated",
        params={"labels[every]": ["label C"]},
        headers=payments_headers,
    )
    assert response.is_success
    data = response.json()
    assert data["total"] == payment_count // 5
    for payment in data["data"]:
        assert "label C" in payment["labels"]

    # search payments by label A and B
    response = await client.get(
        "/api/v1/payments/paginated",
        params={"labels[every]": ["label A", "label B"]},
        headers=payments_headers,
    )
    assert response.is_success
    data = response.json()

    assert data["total"] == payment_count // 6
    for payment in data["data"]:
        assert "label A" in payment["labels"]
        assert "label B" in payment["labels"]

    # search payments for random label D (no payments)
    response = await client.get(
        "/api/v1/payments/paginated",
        params={"labels[every]": ["label D"]},
        headers=payments_headers,
    )
    assert response.is_success
    data = response.json()

    assert data["total"] == 0

    # search payments with no label filter (all payments)
    response = await client.get(
        "/api/v1/payments/paginated",
        params={"labels[every]": []},
        headers=payments_headers,
    )
    assert response.is_success
    all_payments = response.json()

    assert all_payments["total"] == payment_count

    no_label_a_payment = next(
        (
            payment
            for payment in all_payments["data"]
            if "label A" not in payment["labels"]
        ),
        None,
    )
    assert no_label_a_payment is not None
    payment_hash = no_label_a_payment["payment_hash"]
    response = await client.put(
        f"/api/v1/payments/{payment_hash}/labels",
        headers=payments_headers,
        json={"labels": ["label A"]},
    )

    # search payments by label A after update
    response = await client.get(
        "/api/v1/payments/paginated",
        params={"labels[every]": ["label A"]},
        headers=payments_headers,
    )
    assert response.is_success
    data = response.json()
    assert data["total"] == payment_count // 2 + 1  # one more after update
    for payment in data["data"]:
        assert "label A" in payment["labels"]

    # remove label A from all payments
    for payment in all_payments["data"]:
        payment_hash = payment["payment_hash"]
        response = await client.put(
            f"/api/v1/payments/{payment_hash}/labels",
            headers=payments_headers,
            json={"labels": []},
        )

    # search payments by label A (none should have it now)
    response = await client.get(
        "/api/v1/payments/paginated",
        params={"labels[every]": ["label A"]},
        headers=payments_headers,
    )
    assert response.is_success
    data = response.json()
    assert data["total"] == 0


async def _create_some_payments(payment_count: int, client, payments_headers):
    payment_count = 10
    for index in range(1, payment_count + 1):
        labels = []
        if index % 2 == 0:
            labels.append("label A")
        if index % 3 == 0:
            labels.append("label B")
        if index % 5 == 0:
            # User does not have this label, but will be added to the payment.
            labels.append("label C")
        response = await client.post(
            "/api/v1/payments",
            headers=payments_headers,
            json={
                "out": False,
                "amount": 1000 + index,
                "memo": f"payment {index}",
                "labels": labels,
            },
        )
        assert response.is_success
        data = response.json()
        assert data["labels"] == labels
    return payment_count
