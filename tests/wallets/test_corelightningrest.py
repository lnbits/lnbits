from json.decoder import JSONDecodeError

import pytest
from httpx import HTTPStatusError
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from lnbits.wallets.corelightningrest import CoreLightningRestWallet, settings

ENDPONT = "http://127.0.0.1:8555"
MCAROON = "eNcRyPtEdMaCaRoOn"


# specify where the server should bind to
@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8555)


@pytest.mark.asyncio
async def test_status_no_balance(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPONT
    settings.corelightning_rest_macaroon = MCAROON

    httpserver.expect_request("/v1/channel/localremotebal").respond_with_json({})

    wallet = CoreLightningRestWallet()

    status = await wallet.status()
    assert status.error_message == "no data"
    assert status.balance_msat == 0

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_status_with_balance(httpserver: HTTPServer):

    resp = {"localBalance": 55}
    httpserver.expect_request("/v1/channel/localremotebal").respond_with_json(resp)

    settings.corelightning_rest_url = ENDPONT
    settings.corelightning_rest_macaroon = MCAROON
    wallet = CoreLightningRestWallet()

    status = await wallet.status()
    assert status.error_message is None
    assert status.balance_msat == 55000

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_status_with_error(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPONT
    settings.corelightning_rest_macaroon = MCAROON

    resp = {"error": "test-error"}
    httpserver.expect_request("/v1/channel/localremotebal").respond_with_json(resp)

    wallet = CoreLightningRestWallet()

    status = await wallet.status()
    assert (
        status.error_message == f"Failed to connect to {ENDPONT}, got: 'test-error...'"
    )
    assert status.balance_msat == 0

    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_status_with_error_body(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPONT
    settings.corelightning_rest_macaroon = MCAROON

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
    settings.corelightning_rest_url = ENDPONT
    settings.corelightning_rest_macaroon = MCAROON

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
    settings.corelightning_rest_url = ENDPONT
    settings.corelightning_rest_macaroon = MCAROON

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

    settings.corelightning_rest_url = ENDPONT

    with pytest.raises(ValueError) as e_info:
        CoreLightningRestWallet()

    assert (
        str(e_info.value)
        == "cannot initialize CoreLightningRestWallet: "
        + "missing corelightning_rest_macaroon"
    )

    settings.corelightning_rest_macaroon = MCAROON

    wallet = CoreLightningRestWallet()
    assert wallet.url == ENDPONT


@pytest.mark.asyncio
async def test_cleanup(httpserver: HTTPServer):
    settings.corelightning_rest_url = ENDPONT
    settings.corelightning_rest_macaroon = MCAROON

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
