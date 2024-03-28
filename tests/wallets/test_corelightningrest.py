from json.decoder import JSONDecodeError
from urllib.parse import urlencode

import pytest
from httpx import HTTPStatusError
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

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
async def test_status_with_bad_json(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    httpserver.expect_request("/v1/channel/localremotebal").respond_with_data(
        "test-text-error"
    )

    wallet = CoreLightningRestWallet()

    # todo: inconsistent
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


# todo: extract
@pytest.mark.asyncio
async def test_status_for_server_down():
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    wallet = CoreLightningRestWallet()

    with pytest.raises(HTTPStatusError) as e_info:
        await wallet.status()

    assert e_info.match("Server error '500 INTERNAL SERVER ERROR'")


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

    # todo: extract extra
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
            description_hash=None,
            unhashed_description=None,
            **extra_server_resquest,
        )

        assert invoice_resp.success is True
        assert invoice_resp.checking_id == server_resp["payment_hash"]
        assert invoice_resp.payment_request == server_resp["bolt11"]
        assert invoice_resp.error_message is None

        if key:
            del data[key]
        httpserver.check_assertions()


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
async def test_create_invoice_error(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    amount = 555
    server_resp = {"error": "Test Error"}

    data = {
        "amount": amount * 1000,
        "description": "Test Invoice",
        "label": "test-label",
    }

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
    )

    assert invoice_resp.success is False
    assert invoice_resp.checking_id is None
    assert invoice_resp.payment_request is None
    assert invoice_resp.error_message == "Test Error"

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_create_invoice_for_http_404(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    amount = 555

    data = {
        "amount": amount * 1000,
        "description": "Test Invoice",
        "label": "test-label",
    }

    httpserver.expect_request(
        uri="/v1/invoice/genInvoice",
        headers=headers,
        method="POST",
        data=urlencode(data),
    ).respond_with_response(Response("Not Found", status=404))

    wallet = CoreLightningRestWallet()

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


@pytest.mark.asyncio
async def test_pay_invoice_ok(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    fee_limit_msat = 25_000
    server_resp = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96",
        "payment_preimage": "00000000000000000000000000000000"
        + "00000000000000000000000000000000",
        "msatoshi": 21_000,
        "msatoshi_sent": 21_050,
        "status": "paid",
    }

    data = {
        "invoice": bolt11_sample,
        "maxfeepercent": f"{(fee_limit_msat / 21_000 * 100):.11}",
        "exemptfee": 0,
    }

    httpserver.expect_request(
        uri="/v1/pay",
        headers=headers,
        method="POST",
        data=urlencode(data),
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    invoice_resp = await wallet.pay_invoice(bolt11_sample, fee_limit_msat)

    assert invoice_resp.success is True
    assert invoice_resp.checking_id == server_resp["payment_hash"]
    assert invoice_resp.fee_msat == 50
    assert (
        invoice_resp.preimage
        == "00000000000000000000000000000000" + "00000000000000000000000000000000"
    )
    assert invoice_resp.error_message is None

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_pay_invoice_error_response(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    fee_limit_msat = 25_000
    server_resp = {"error": "Test Error"}

    data = {
        "invoice": bolt11_sample,
        "maxfeepercent": f"{(fee_limit_msat / 21_000 * 100):.11}",
        "exemptfee": 0,
    }

    httpserver.expect_request(
        uri="/v1/pay",
        headers=headers,
        method="POST",
        data=urlencode(data),
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    invoice_resp = await wallet.pay_invoice(bolt11_sample, fee_limit_msat)

    assert invoice_resp.success is False
    assert invoice_resp.error_message == "Test Error"
    assert invoice_resp.checking_id is None
    assert invoice_resp.fee_msat is None
    assert invoice_resp.preimage is None

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_pay_invoice_http_404(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    fee_limit_msat = 25_000
    data = {
        "invoice": bolt11_sample,
        "maxfeepercent": f"{(fee_limit_msat / 21_000 * 100):.11}",
        "exemptfee": 0,
    }

    httpserver.expect_request(
        uri="/v1/pay",
        headers=headers,
        method="POST",
        data=urlencode(data),
    ).respond_with_response(Response("Not Found", status=404))

    wallet = CoreLightningRestWallet()

    invoice_resp = await wallet.pay_invoice(bolt11_sample, fee_limit_msat)

    assert invoice_resp.success is False
    assert invoice_resp.error_message == "Not Found"

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_invoice_status_success(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    server_resp = {"invoices": [{"status": "paid"}]}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/invoice/listInvoices",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is True
    assert status.failed is False
    assert status.pending is False

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_invoice_status_failed(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    server_resp = {"invoices": [{"status": "failed"}]}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/invoice/listInvoices",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is True
    # todo: this needs fixing in "PaymentStatus"
    # assert status.pending is False

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_invoice_status_pending(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    server_resp = {"invoices": [{"status": "pending"}]}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/invoice/listInvoices",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_invoice_status_error_response(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    server_resp = {"error": "Test Error"}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/invoice/listInvoices",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_invoice_status_http_404(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/invoice/listInvoices",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_response(Response("Not Found", status=404))

    wallet = CoreLightningRestWallet()

    status = await wallet.get_invoice_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_success(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    server_resp = {
        "pays": [
            {
                "status": "complete",
                "amount_msat": "21000msat",
                "amount_sent_msat": "-22000msat",
                "preimage": "00000000000000000000000000000000"
                + "00000000000000000000000000000000",
            }
        ]
    }

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/pay/listPays",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.get_payment_status(params["payment_hash"])

    assert status.fee_msat == 1000
    assert status.preimage == server_resp["pays"][0]["preimage"]
    assert status.success is True
    assert status.failed is False
    assert status.pending is False

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_pending(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    server_resp = {"pays": [{"status": "pending"}]}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/pay/listPays",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()
    status = await wallet.get_payment_status(params["payment_hash"])

    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_failed(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    server_resp = {"pays": [{"status": "failed"}]}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/pay/listPays",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.get_payment_status(params["payment_hash"])

    assert status.success is False
    assert status.failed is True

    # todo: this needs fixing in "PaymentStatus"
    # assert status.pending is False

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_error_response(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    server_resp = {"error": "Test Error"}

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/pay/listPays",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_json(server_resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.get_payment_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_payment_status_http_404(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPOINT
    settings.corelightning_rest_macaroon = MACAROON

    params = {
        "payment_hash": "e35526a43d04e985594c0dfab848814f"
        + "524b1c786598ec9a63beddb2d726ac96"
    }
    httpserver.expect_request(
        uri="/v1/pay/listPays",
        headers=headers,
        query_string=params,
        method="GET",
    ).respond_with_response(Response("Not Found", status=404))

    wallet = CoreLightningRestWallet()

    status = await wallet.get_payment_status(params["payment_hash"])
    assert status.success is False
    assert status.failed is False
    assert status.pending is True

    httpserver.check_assertions()
