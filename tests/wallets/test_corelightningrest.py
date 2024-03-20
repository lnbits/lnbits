from json.decoder import JSONDecodeError
from urllib.parse import urlencode

import pytest
from httpx import HTTPStatusError
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from lnbits.wallets.corelightningrest import CoreLightningRestWallet, settings

ENDPOINT = "http://127.0.0.1:8555"
MACAROON = "eNcRyPtEdMaCaRoOn"

headers = {
    "macaroon": MACAROON,
    "encodingtype": "hex",
    "accept": "application/json",
    "User-Agent": settings.user_agent,
}

bolt11_sample = str(
    "lnbc210n1pjlgal5sp5xr3uwlfm7ltum"
    + "djyukhys0z2rw6grgm8me9k4w9vn05zt"
    + "9svzzjspp5ud2jdfpaqn5c2k2vphatsj"
    + "ypfafyk8rcvkvwexnrhmwm94ex4jtqdq"
    + "u24hxjapq23jhxapqf9h8vmmfvdjscqp"
    + "jrzjqta942048v7qxh5x7pxwplhmtwfl"
    + "0f25cq23jh87rhx7lgrwwvv86r90guqq"
    + "nwgqqqqqqqqqqqqqqpsqyg9qxpqysgqy"
    + "lngsyg960lltngzy90e8n22v4j2hvjs4"
    + "l4ttuy79qqefjv8q87q9ft7uhwdjakvn"
    + "sgk44qyhalv6ust54x98whl3q635hkwgsyw8xgqjl7jwu",
)


# specify where the server should bind to
@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8555)


@pytest.mark.asyncio
async def test_status_no_balance(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    httpserver.expect_request(
        uri="/v1/channel/localremotebal", headers=headers, method="GET"
    ).respond_with_json({})

    wallet = CoreLightningRestWallet()

    status = await wallet.status()
    assert status.error_message == "no data"
    assert status.balance_msat == 0

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_status_with_balance(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    resp = {"localBalance": 55}
    httpserver.expect_request("/v1/channel/localremotebal").respond_with_json(resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.status()
    assert status.error_message is None
    assert status.balance_msat == 55000

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_status_with_error(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    resp = {"error": "test-error"}
    httpserver.expect_request("/v1/channel/localremotebal").respond_with_json(resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.status()
    assert (
        status.error_message == f"Failed to connect to {ENDPOINT}, got: 'test-error...'"
    )
    assert status.balance_msat == 0

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_status_with_error_body(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    httpserver.expect_request("/v1/channel/localremotebal").respond_with_data(
        "test-text-error"
    )

    wallet = CoreLightningRestWallet()

    with pytest.raises(JSONDecodeError) as e_info:
        await wallet.status()

    assert str(e_info.value) == "Expecting value: line 1 column 1 (char 0)"

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_status_for_http_404(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    httpserver.expect_request("/v1/channel/localremotebal").respond_with_response(
        Response("Not Found", status=404)
    )

    wallet = CoreLightningRestWallet()

    with pytest.raises(HTTPStatusError) as e_info:
        await wallet.status()

    assert e_info.match("Client error '404 NOT FOUND'")

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_status_for_server_down():
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    wallet = CoreLightningRestWallet()

    with pytest.raises(HTTPStatusError) as e_info:
        await wallet.status()

    assert e_info.match("Server error '500 INTERNAL SERVER ERROR'")


@pytest.mark.asyncio
async def test_status_for_missing_config():
    settings.corelightning_rest_url = None
    settings.corelightning_rest_macaroon = None

    with pytest.raises(ValueError) as e_info:
        CoreLightningRestWallet()

    assert (
        str(e_info.value)
        == "cannot initialize CoreLightningRestWallet: "
        + "missing corelightning_rest_url"
    )

    settings.corelightning_rest_url = ENDPOINT

    with pytest.raises(ValueError) as e_info:
        CoreLightningRestWallet()

    assert (
        str(e_info.value)
        == "cannot initialize CoreLightningRestWallet: "
        + "missing corelightning_rest_macaroon"
    )

    settings.corelightning_rest_macaroon = MACAROON

    wallet = CoreLightningRestWallet()
    assert wallet.url == ENDPOINT


@pytest.mark.asyncio
async def test_cleanup(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    resp = {"localBalance": 55}
    httpserver.expect_request("/v1/channel/localremotebal").respond_with_json(resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.status()
    assert status.error_message is None
    assert status.balance_msat == 55000

    # all calls should fail after this method is called
    await wallet.cleanup()

    with pytest.raises(RuntimeError) as e_info:
        # expected to fail
        await wallet.status()

    assert str(e_info.value) == "Cannot send a request, as the client has been closed."


@pytest.mark.asyncio
async def test_create_invoice_ok(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    amount = 555
    server_resp = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96",
        "bolt11": bolt11_sample,
    }

    data = {
        "amount": amount * 1000,
        "description": "Test Invoice",
        "label": "test-label",
    }

    extra_data = {None: None, "expiry": 123, "preimage": "xxx"}

    for key in extra_data:
        extra_server_resquest = {}
        if key:
            data[key] = extra_data[key]
            extra_server_resquest[key] = extra_data[key]

        httpserver.clear_all_handlers()
        httpserver.expect_request(
            uri="/v1/invoice/genInvoice",
            headers=headers,
            method="POST",
            data=urlencode(data),
        ).respond_with_json(server_resp)

        wallet = CoreLightningRestWallet()

        invoice_resp = await wallet.create_invoice(
            amount=amount,
            memo="Test Invoice",
            label="test-label",
            **extra_server_resquest,
        )

        assert invoice_resp.success is True
        assert invoice_resp.checking_id == server_resp["payment_hash"]
        assert invoice_resp.payment_request == server_resp["bolt11"]
        assert invoice_resp.error_message is None

        if key:
            del data[key]
        httpserver.check_assertions()
