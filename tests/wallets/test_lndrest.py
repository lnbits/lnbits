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
async def test_cleanup(httpserver: HTTPServer):
    pytest.skip("todo: extract")
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
