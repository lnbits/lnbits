import importlib
import json
from typing import Dict, Union
from urllib.parse import urlencode

import pytest
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from lnbits.core.models import BaseWallet
from tests.helpers import FundingSourceConfig, Mock, rest_wallet_fixtures_from_json

wallets_module = importlib.import_module("lnbits.wallets")

# todo:
# - tests for extra fields
# - tests for paid_invoices_stream
# - test particular validations


# specify where the server should bind to
@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8555)


def build_test_id(test):
    return f"""{test["funding_source"]}.{test["function"]}({test["description"]})"""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_data",
    rest_wallet_fixtures_from_json("tests/wallets/fixtures3.json"),
    ids=build_test_id,
)
async def test_rest_wallet(httpserver: HTTPServer, test_data: dict):
    for mock in test_data["mocks"]:
        _apply_mock(httpserver, mock)

    wallet = _load_funding_source(test_data["funding_source"])
    await _check_assertions(wallet, test_data)


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


async def _check_assertions(wallet, test_data):
    tested_func = test_data["function"]
    call_params = test_data["call_params"]

    if "expect" in test_data:
        await _assert_data(wallet, tested_func, call_params, test_data["expect"])
        # if len(test_data["mocks"]) == 0:
        #     # all calls should fail after this method is called
        #     await wallet.cleanup()
        #     # same behaviour expected is server canot be reached
        #     # or if the connection was closed
        #     await _assert_data(wallet, tested_func, call_params, test_data["expect"])
    elif "expect_error" in test_data:
        await _assert_error(wallet, tested_func, call_params, test_data["expect_error"])
    else:
        assert False, "Expected outcome not specified"


async def _assert_data(wallet, tested_func, call_params, expect):
    resp = await getattr(wallet, tested_func)(**call_params)
    for key in expect:
        received = getattr(resp, key)
        expected = expect[key]
        assert (
            getattr(resp, key) == expect[key]
        ), f"""Field "{key}". Received: "{received}". Expected: "{expected}"."""


async def _assert_error(wallet, tested_func, call_params, expect_error):
    error_module = importlib.import_module(expect_error["module"])
    error_class = getattr(error_module, expect_error["class"])
    with pytest.raises(error_class) as e_info:
        await getattr(wallet, tested_func)(**call_params)

    assert e_info.match(expect_error["message"])


def _load_funding_source(funding_source: FundingSourceConfig) -> BaseWallet:
    custom_settings = funding_source.settings | {"user_agent": "LNbits/Tests"}
    original_settings = {}

    settings = getattr(wallets_module, "settings")

    for s in custom_settings:
        original_settings[s] = getattr(settings, s)
        setattr(settings, s, custom_settings[s])

    fs_instance: BaseWallet = getattr(wallets_module, funding_source.wallet_class)()

    # rollback settings (global variable)
    for s in original_settings:
        setattr(settings, s, original_settings[s])

    return fs_instance
