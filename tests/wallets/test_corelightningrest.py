import pytest
from pytest_httpserver import HTTPServer

from lnbits.wallets.corelightningrest import CoreLightningRestWallet, settings

ENDPONT = "http://127.0.0.1:8555"
MCAROON = "eNcRyPtEdMaCaRoOn"


# specify where the server should bind to
@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8555)


@pytest.mark.asyncio
async def test_status_no_balance(httpserver: HTTPServer):

    httpserver.expect_request("/v1/channel/localremotebal").respond_with_json({})

    settings.corelightning_rest_url = ENDPONT
    settings.corelightning_rest_macaroon = MCAROON
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
