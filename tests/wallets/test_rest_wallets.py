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

        print("### tests", tests)
        return tests


def _load_funding_sources(data: dict) -> dict:
    funding_sources = {}
    for fs_name in data:
        funding_source = data[fs_name]

        funding_sources[fs_name] = getattr(wallets_module, funding_source["class"])

        settings = getattr(wallets_module, "settings")
        for s in funding_source["settings"]:
            setattr(settings, s, funding_source["settings"][s])

    print("### funding_sources", funding_sources)
    return funding_sources


# specify where the server should bind to
@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 8555)


@pytest.fixture(params=load_tests_from_json("tests/wallets/fixtures3.json"))
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
        **request_data,  # type: ignore
    )

    if test["response_type"] == "response":
        server_response = Response(**server_response)

    getattr(req, respond_with)(server_response)

    parameters = test["params"] if "params" in test else {}
    wallet = test_data["wallet_class"]()

    print("### test", test)

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


### Test Sample
# "my_func_01": [
#     {
#         "description": "create ok",
#         "call_params": {},
#         "expect": {},
#         "mock_server": {
#             "corelightningrest": {
#                 "request_type": "data",
#                 "request_body": {},
#                 "response_type": "json",
#                 "response": {}
#             },
#             "lndrest": {
#                 "request_type": "json",
#                 "request_body": {},
#                 "response_type": "json",
#                 "response": {}
#             }
#         }
#     }
# ],
