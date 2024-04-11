import json
from typing import Dict, Union
from urllib.parse import urlencode

import pytest
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from tests.wallets.helpers import (
    Mock,
    WalletTest,
    build_test_id,
    check_assertions,
    load_funding_source,
    rest_wallet_fixtures_from_json,
)

# todo:
# - tests for extra fields
# - tests for paid_invoices_stream
# - test particular validations


# specify where the server should bind to
@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8555)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_data",
    rest_wallet_fixtures_from_json("tests/wallets/fixtures.json"),
    ids=build_test_id,
)
async def test_rest_wallet(httpserver: HTTPServer, test_data: WalletTest):
    if test_data.skip:
        pytest.skip()

    for mock in test_data.mocks:
        _apply_mock(httpserver, mock)

    wallet = load_funding_source(test_data.funding_source)
    await check_assertions(wallet, test_data)


def _apply_mock(httpserver: HTTPServer, mock: Mock):

    request_data: Dict[str, Union[str, dict]] = {}
    request_type = getattr(mock.dict(), "request_type", None)
    # request_type = mock.request_type <--- this des not work for whatever reason!!!

    if request_type == "data":
        assert isinstance(mock.response, dict), "request data must be JSON"
        request_data["data"] = urlencode(mock.response)
    elif request_type == "json":
        request_data["json"] = mock.response

    if mock.query_params:
        request_data["query_string"] = mock.query_params

    assert mock.uri, "Missing URI for HTTP mock."
    assert mock.method, "Missing method for HTTP mock."
    req = httpserver.expect_request(
        uri=mock.uri,
        headers=mock.headers,
        method=mock.method,
        **request_data,  # type: ignore
    )

    server_response: Union[str, dict, Response] = mock.response
    response_type = mock.response_type
    if response_type == "response":
        assert isinstance(server_response, dict), "server response must be JSON"
        server_response = Response(**server_response)
    elif response_type == "stream":
        response_type = "response"
        server_response = Response(iter(json.dumps(server_response).splitlines()))

    respond_with = f"respond_with_{response_type}"

    getattr(req, respond_with)(server_response)
