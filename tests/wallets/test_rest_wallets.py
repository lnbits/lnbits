import importlib
import json
from urllib.parse import urlencode

import pytest
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

wallets_module = importlib.import_module("lnbits.wallets")

# todo:
#  - fix user agent


def load_tests_from_json(path):
    with open(path) as f:
        data = json.load(f)

        funding_sources = _load_funding_sources(data["funding_sources"])

        tests = {fs_name: [] for fs_name in funding_sources}

        for fn_name in data["functions"]:
            fn = data["functions"][fn_name]

            for test in fn["tests"]:
                """create an unit test for each funding source"""

                for fs_name in funding_sources:
                    fs_mocks = fn["mocks"][fs_name]
                    test_mocks = test["mocks"][fs_name]
                    t = (
                        {
                            "wallet_class": funding_sources[fs_name],
                            "function": fn_name,
                        }
                        | {**test}
                        | {"mocks": []}
                    )

                    for mock_name in fs_mocks:
                        t["mocks"].append(fs_mocks[mock_name] | test_mocks[mock_name])

                    tests[fs_name].append(t)

        return sum([tests[fs_name] for fs_name in tests], [])


def _load_funding_sources(data: dict) -> dict:
    funding_sources = {}
    for fs_name in data:
        funding_source = data[fs_name]

        funding_sources[fs_name] = getattr(wallets_module, funding_source["class"])

        settings = getattr(wallets_module, "settings")
        for s in funding_source["settings"]:
            setattr(settings, s, funding_source["settings"][s])

    return funding_sources


# specify where the server should bind to
@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8555)


@pytest.fixture(params=load_tests_from_json("tests/wallets/fixtures3.json"))
def test_data(request):
    return request.param


@pytest.mark.asyncio
async def test_rest_wallet(httpserver: HTTPServer, test_data: dict):
    for mock in test_data["mocks"]:
        _apply_mock(httpserver, mock)

    wallet = test_data["wallet_class"]()
    await _check_assertions(wallet, test_data)


def _apply_mock(httpserver: HTTPServer, mock: dict):
    request_data = {}
    request_type = getattr(mock, "request_type", None)

    if request_type == "data":
        request_data["data"] = urlencode(mock["response"])
    elif request_type == "json":
        request_data["json"] = mock["response"]

    req = httpserver.expect_request(
        uri=mock["uri"],
        headers=mock["headers"],
        method=mock["method"],
        **request_data,  # type: ignore
    )

    server_response = mock["response"]
    if mock["response_type"] == "response":
        server_response = Response(**server_response)

    respond_with = f"""respond_with_{mock["response_type"]}"""
    getattr(req, respond_with)(server_response)


async def _check_assertions(wallet, test_data):
    tested_func = test_data["function"]
    call_params = test_data["call_params"]

    if "expect" in test_data:
        await _assert_data(wallet, tested_func, call_params, test_data["expect"])
    elif "expect_error" in test_data:
        await _assert_error(wallet, tested_func, call_params, test_data["expect_error"])
    else:
        assert False, "Expected outcome not specified"


async def _assert_data(wallet, tested_func, call_params, expect):
    resp = await getattr(wallet, tested_func)(**call_params)
    for key in expect:
        assert getattr(resp, key) == expect[key]


async def _assert_error(wallet, tested_func, call_params, expect_error):
    error_module = importlib.import_module(expect_error["module"])
    error_class = getattr(error_module, expect_error["class"])
    with pytest.raises(error_class) as e_info:
        await getattr(wallet, tested_func)(**call_params)

    assert e_info.match(expect_error["message"])
