from urllib.parse import urlencode

import pytest
from pytest_httpserver import HTTPServer

from lnbits.wallets.base import Unsupported
from lnbits.wallets.corelightningrest import CoreLightningRestWallet, settings

ENDPOINT = "http://127.0.0.1:8555"
MACAROON = "eNcRyPtEdMaCaRoOn"


headers = {
    "macaroon": MACAROON,
    "encodingtype": "hex",
    "accept": "application/json",
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


# todo: extract
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


# todo: extract
@pytest.mark.asyncio
async def test_cleanup(httpserver: HTTPServer):
    pytest.skip("todo: extract")
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


# todo: extract
@pytest.mark.asyncio
async def test_create_invoice_unhashed_description(httpserver: HTTPServer):
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
        "description": "hhh",
        "label": "test-label",
    }

    httpserver.expect_request(
        uri="/v1/invoice/genInvoice",
        headers=headers,
        method="POST",
        data=urlencode(data),
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    with pytest.raises(Unsupported) as e_info:
        invoice_resp = await wallet.create_invoice(
            amount=amount,
            memo="Test Invoice",
            label="test-label",
            description_hash="24d166cd6c8b826c779040b49d5b6708d649b236558e8744339dfee6afe11999".encode(),
            unhashed_description=None,
        )

    assert e_info.match(
        "'description_hash' unsupported by CoreLightningRest, "
        + "provide 'unhashed_description'"
    )

    invoice_resp = await wallet.create_invoice(
        amount=amount,
        memo="Test Invoice",
        label="test-label",
        description_hash="24d166cd6c8b826c779040b49d5b6708d649b236558e8744339dfee6afe11999".encode(),
        unhashed_description="hhh".encode(),
    )

    assert invoice_resp.success is True
    assert invoice_resp.checking_id == server_resp["payment_hash"]
    assert invoice_resp.payment_request == server_resp["bolt11"]
    assert invoice_resp.error_message is None

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_pay_invoice_validation():
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    wallet = CoreLightningRestWallet()

    status = await wallet.pay_invoice("bad_bolt11", 5)
    assert status.ok is False
    assert status.error_message == "Bech32 string is not valid."

    bolt11_zero_sats = str(
        "lnbc1pjl4cvppp5n2ekurjn0t0lfjrls"
        + "5vtja3hl5vq0xp4eelxyrv3ej4snekcq"
        + "9jqdqlf38xy6t5wvs9getnwssyjmnkda"
        + "5kxegcqzzsxqyz5vqsp5pl0surycfpw9"
        + "vmxw25fnlvsnq39ngmrg8ztsv8fu9y8c"
        + "myq2t8vs9qyyssqfwahs65kvvmusamrg"
        + "yh32r2zycam3sfzngjfk8g0yrk77hxdh"
        + "wehu0l5v5a7r4mw45s3zay72tnaxvwzn"
        + "mfrzw3pnrafmdxyqhr898sp6k5v0r"
    )

    status = await wallet.pay_invoice(bolt11_zero_sats, 5)
    assert status.ok is False
    assert status.error_message == "0 amount invoices are not allowed"
