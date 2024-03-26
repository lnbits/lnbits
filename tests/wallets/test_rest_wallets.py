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

        tests = []
        for funding_source in data:
            wallet = data[funding_source]

            wallet_class = getattr(wallets_module, wallet["class"])
            settings = getattr(wallets_module, "settings")
            for s in wallet["settings"]:
                setattr(settings, s, wallet["settings"][s])

            for func in wallet["api"]:
                for test in wallet["api"][func]["tests"]:
                    tests.append(
                        {
                            "wallet_class": wallet_class,
                            "function": func,
                            "server": wallet["api"][func]["server"],
                            "test": test,
                        }
                    )

        return tests


# specify where the server should bind to
@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8555)


@pytest.fixture(params=load_tests_from_json("tests/wallets/fixtures.json"))
def test_data(request):
    return request.param


@pytest.mark.asyncio
async def test_rest_wallet(httpserver: HTTPServer, test_data):
    server = test_data["server"]
    test = test_data["test"]
    respond_with = f"""respond_with_{test["response_type"]}"""
    server_response = test["server_response"]

    request_data = {}
    if "data" in test:
        request_data["data"] = urlencode(test["data"])
    elif "json" in test:
        request_data["json"] = test["json"]

    req = httpserver.expect_request(
        uri=server["uri"],
        headers=server["headers"],
        method=server["method"],
        **request_data,
    )

    if test["response_type"] == "response":
        server_response = Response(**server_response)

    getattr(req, respond_with)(server_response)

    parameters = test["params"] if "params" in test else {}
    wallet = test_data["wallet_class"]()

    if "expect" in test:
        resp = await getattr(wallet, test_data["function"])(**parameters)
        for key in test["expect"]:
            assert getattr(resp, key) == test["expect"][key]

    elif "expect_error" in test:
        error_module = importlib.import_module(test["expect_error"]["module"])
        error_class = getattr(error_module, test["expect_error"]["class"])
        with pytest.raises(error_class) as e_info:
            await getattr(wallet, test_data["function"])(**parameters)

        assert e_info.match(test["expect_error"]["message"])
    else:
        assert False, "Expected outcome not specified"
