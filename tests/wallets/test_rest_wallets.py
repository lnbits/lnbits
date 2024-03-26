import importlib
import json

import pytest
from pytest_httpserver import HTTPServer

wallets_module = importlib.import_module("lnbits.wallets")


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
async def test_status_no_balance(httpserver: HTTPServer, test_data):
    print("### test_status_no_balance: ", test_data)

    server = test_data["server"]
    print("### server", server)
    httpserver.expect_request(
        uri=server["uri"], headers=server["headers"], method=server["method"]
    ).respond_with_json(test_data["test"]["server_response"])


    wallet = test_data["wallet_class"]()


    resp = await getattr(wallet, test_data["function"])()
    print("### resp", resp)
    for key in test_data["test"]["expect"]:
        assert getattr(resp, key) == test_data["test"]["expect"][key]
    # assert status.error_message == "no data"
    # assert status.balance_msat == 0
