import json

import pytest
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from lnbits.wallets.corelightningrest import settings
from lnbits.wallets.lndrest import LndRestWallet

ENDPOINT = "http://127.0.0.1:8555"
MACAROON = "eNcRyPtEdMaCaRoOn"

headers = {
    "Grpc-Metadata-macaroon": MACAROON,
    "User-Agent": "LNbits/Tests",
}

settings.user_agent = "LNbits/Tests"


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
async def test_status_for_missing_config():
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    # todo


@pytest.mark.asyncio
@pytest.skip("todo: extract")
async def test_cleanup(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    server_response = {"balance": 21}
    httpserver.expect_request(
        uri="/v1/balance/channels", headers=headers, method="GET"
    ).respond_with_json(server_response)

    wallet = LndRestWallet()

    status = await wallet.status()
    assert status.error_message is None
    assert status.balance_msat == 21_000

    # all calls should fail after this method is called
    await wallet.cleanup()

    with pytest.raises(RuntimeError) as e_info:
        # expected to fail
        await wallet.status()

    assert str(e_info.value) == "Cannot send a request, as the client has been closed."


# todo
# @pytest.mark.asyncio
# async def test_create_invoice_unhashed_description(httpserver: HTTPServer):
#     settings.lnd_rest_endpoint = ENDPOINT
#     settings.lnd_rest_macaroon = MACAROON
#     settings.lnd_rest_cert = ""


@pytest.mark.asyncio
async def test_create_invoice_error(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    amount = 555
    server_resp = {"error": "Test Error"}

    data = {"value": amount, "memo": "Test Invoice", "private": True}

    httpserver.expect_request(
        uri="/v1/invoices",
        headers=headers,
        method="POST",
        json=data,
    ).respond_with_json(
        server_resp, 400
    )  # todo: extra HTTP status

    wallet = LndRestWallet()

    invoice_resp = await wallet.create_invoice(
        amount=amount,
        memo="Test Invoice",
        label="test-label",
    )

    assert invoice_resp.success is False
    assert invoice_resp.checking_id is None
    assert invoice_resp.payment_request is None
    assert invoice_resp.error_message == "Test Error"

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_create_invoice_for_http_404(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    amount = 555

    data = {
        "amount": amount * 1000,
        "description": "Test Invoice",
        "label": "test-label",
    }

    data = {"value": amount, "memo": "Test Invoice", "private": True}

    httpserver.expect_request(
        uri="/v1/invoices", headers=headers, method="POST", json=data
    ).respond_with_response(Response("Not Found", status=404))

    wallet = LndRestWallet()

    invoice_resp = await wallet.create_invoice(
        amount=amount,
        memo="Test Invoice",
        label="test-label",
    )

    assert invoice_resp.success is False
    assert invoice_resp.checking_id is None
    assert invoice_resp.payment_request is None
    assert invoice_resp.error_message == "Not Found"

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_pay_invoice_validation():
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    # wallet = LndRestWallet()

    # todo: add validation in wallet
    # status = await wallet.pay_invoice("bad_bolt11", 5)
    # assert status.ok is False
    # assert status.error_message == "Bech32 string is not valid."

    # todo: block zero amount invoices in wallet
    # bolt11_zero_sats = str(
    #     "lnbc1pjl4cvppp5n2ekurjn0t0lfjrls"
    #     + "5vtja3hl5vq0xp4eelxyrv3ej4snekcq"
    #     + "9jqdqlf38xy6t5wvs9getnwssyjmnkda"
    #     + "5kxegcqzzsxqyz5vqsp5pl0surycfpw9"
    #     + "vmxw25fnlvsnq39ngmrg8ztsv8fu9y8c"
    #     + "myq2t8vs9qyyssqfwahs65kvvmusamrg"
    #     + "yh32r2zycam3sfzngjfk8g0yrk77hxdh"
    #     + "wehu0l5v5a7r4mw45s3zay72tnaxvwzn"
    #     + "mfrzw3pnrafmdxyqhr898sp6k5v0r"
    # )

    # status = await wallet.pay_invoice(bolt11_zero_sats, 5)
    # assert status.ok is False
    # assert status.error_message == "0 amount invoices are not allowed"


@pytest.mark.asyncio
async def test_pay_invoice_ok(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    fee_limit_msat = 25_000
    fee_msat = 1000
    server_resp = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96",
        "payment_route": {"total_fees_msat": fee_msat},
        "payment_preimage": "00000000000000000000000000000000"
        + "00000000000000000000000000000000",
    }

    data = {
        "payment_request": bolt11_sample,
        "fee_limit": {"fixed_msat": f"{fee_limit_msat}"},
    }

    httpserver.expect_request(
        uri="/v1/channels/transactions", headers=headers, method="POST", json=data
    ).respond_with_json(server_resp)

    wallet = LndRestWallet()

    invoice_resp = await wallet.pay_invoice(bolt11_sample, fee_limit_msat)

    assert invoice_resp.success is True
    assert invoice_resp.fee_msat == fee_msat
    assert (
        invoice_resp.checking_id
        == "7b7e79dba6b8dddd387bdf39e7de1cd1"
        + "d7da6fce3cf35e1fe76e1bd5cefceb9"
        + "f7c79cf5aeb76de75d6f677bdba69cf7a"
    )
    assert (
        invoice_resp.preimage
        == "d34d34d34d34d34d34d34d34d34d34d3"
        + "4d34d34d34d34d34d34d34d34d34d34d"
        + "34d34d34d34d34d34d34d34d34d34d34"
    )
    assert invoice_resp.error_message is None

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_pay_invoice_error_response(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    fee_limit_msat = 25_000
    server_resp = {"payment_error": "Test Error"}

    data = {
        "payment_request": bolt11_sample,
        "fee_limit": {"fixed_msat": f"{fee_limit_msat}"},
    }

    httpserver.expect_request(
        uri="/v1/channels/transactions", headers=headers, method="POST", json=data
    ).respond_with_json(server_resp)

    wallet = LndRestWallet()

    invoice_resp = await wallet.pay_invoice(bolt11_sample, fee_limit_msat)

    assert invoice_resp.success is False
    assert invoice_resp.error_message == "Test Error"
    assert invoice_resp.checking_id is None
    assert invoice_resp.fee_msat is None
    assert invoice_resp.preimage is None

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_pay_invoice_http_404(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    fee_limit_msat = 25_000
    data = {
        "payment_request": bolt11_sample,
        "fee_limit": {"fixed_msat": f"{fee_limit_msat}"},
    }

    httpserver.expect_request(
        uri="/v1/channels/transactions", headers=headers, method="POST", json=data
    ).respond_with_response(Response("Not Found", status=404))

    wallet = LndRestWallet()

    invoice_resp = await wallet.pay_invoice(bolt11_sample, fee_limit_msat)

    assert invoice_resp.success is False
    # todo: incosistency in wallet
    assert invoice_resp.error_message
    assert invoice_resp.error_message.startswith(
        "Client error '404 NOT FOUND' for url "
        + "'http://127.0.0.1:8555/v1/channels/transactions'"
    )

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_invoice_status_success(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    server_resp = {"settled": True}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri=f"""/v1/invoice/{params["payment_hash"]}""",  # todo: changed
        headers=headers,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = LndRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is True
    assert status.failed is False
    assert status.pending is False

    httpserver.check_assertions()


# todo: no fail on LND
# @pytest.mark.asyncio
# async def test_get_invoice_status_failed(httpserver: HTTPServer):
#     settings.corelightning_rest_url = ENDPOINT
#     settings.corelightning_rest_macaroon = MACAROON


@pytest.mark.asyncio
async def test_get_invoice_status_pending(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    server_resp = {"settled": False}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri=f"""/v1/invoice/{params["payment_hash"]}""",  # todo: changed
        headers=headers,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = LndRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_invoice_status_error_response(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    server_resp = {"key": "random json data"}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri=f"""/v1/invoice/{params["payment_hash"]}""",  # todo: changed
        headers=headers,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = LndRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_invoice_status_http_404(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri=f"""/v1/invoice/{params["payment_hash"]}""",  # todo: changed
        headers=headers,
        method="GET",
    ).respond_with_response(Response("Not Found", status=404))

    wallet = LndRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_success(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    server_resp = {
        "result": {
            "status": "SUCCEEDED",
            "fee_msat": 1000,
            "payment_preimage": "00000000000000000000000000000000"
            + "00000000000000000000000000000000",
        }
    }

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v2/router/track/"
        + "41UmpD0E6YVZTA36uEiBT1JLHHhlmOyaY77dstcmrJY=",  # todo: changed
        headers=headers,
        method="GET",
    ).respond_with_response(
        response=Response(iter(json.dumps(server_resp).splitlines()))
    )

    wallet = LndRestWallet()

    status = await wallet.get_payment_status(params["payment_hash"])

    assert status.fee_msat == 1000
    assert status.preimage == server_resp["result"]["payment_preimage"]
    assert status.success is True
    assert status.failed is False
    assert status.pending is False

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_pending(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    server_resp = {"result": {"status": "IN_FLIGHT"}}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v2/router/track/"
        + "41UmpD0E6YVZTA36uEiBT1JLHHhlmOyaY77dstcmrJY=",  # todo: changed
        headers=headers,
        method="GET",
    ).respond_with_response(Response(iter(json.dumps(server_resp).splitlines())))

    wallet = LndRestWallet()

    status = await wallet.get_payment_status(params["payment_hash"])

    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_failed(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    server_responses = [
        {"result": {"status": "FAILED"}},
        {"error": {"code": 5, "message": "payment isn't initiated"}},
    ]

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    for server_resp in server_responses:
        httpserver.clear_all_handlers()
        httpserver.expect_request(
            uri="/v2/router/track/"
            + "41UmpD0E6YVZTA36uEiBT1JLHHhlmOyaY77dstcmrJY=",  # todo: changed
            headers=headers,
            method="GET",
        ).respond_with_response(Response(iter(json.dumps(server_resp).splitlines())))

        wallet = LndRestWallet()

        status = await wallet.get_payment_status(params["payment_hash"])

        assert status.success is False
        assert status.failed is True
        # todo: this needs fixing in "PaymentStatus"
        # assert status.pending is False

        httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_http_404(httpserver: HTTPServer):
    settings.lnd_rest_endpoint = ENDPOINT
    settings.lnd_rest_macaroon = MACAROON
    settings.lnd_rest_cert = ""

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v2/router/track/"
        + "41UmpD0E6YVZTA36uEiBT1JLHHhlmOyaY77dstcmrJY=",  # todo: changed
        headers=headers,
        method="GET",
    ).respond_with_response(Response("Not Found", status=404))

    wallet = LndRestWallet()

    status = await wallet.get_payment_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()
