import importlib
import json
from typing import Dict, List

import pytest

from lnbits.core.models import BaseWallet
from tests.wallets.fixtures.models import FundingSourceConfig, Mock, WalletTest

wallets_module = importlib.import_module("lnbits.wallets")


def rest_wallet_fixtures_from_json(path) -> List["WalletTest"]:
    with open(path) as f:
        data = json.load(f)

        funding_sources = data["funding_sources"]

        tests: Dict[str, List[WalletTest]] = {
            fs_name: [] for fs_name in funding_sources
        }

        for fn_name in data["functions"]:
            fn = data["functions"][fn_name]

            x1(funding_sources, tests, fn_name, fn)

        all_tests = sum([tests[fs_name] for fs_name in tests], [])
        return all_tests


def x1(funding_sources, tests, fn_name, fn):
    for test in fn["tests"]:
        """create an unit test for each funding source"""

        x2(funding_sources, tests, fn_name, fn, test)


def x2(funding_sources, tests, fn_name, fn, test):
    for fs_name in funding_sources:
        funding_source = FundingSourceConfig(**funding_sources[fs_name])
        tests[fs_name] += _tests_for_funding_source(
            fn_name, fs_name, fn, test, funding_source
        )


def _tests_for_funding_source(
    fn_name: str, fs_name: str, fn, test, funding_source: FundingSourceConfig
) -> List[WalletTest]:
    t = WalletTest(
        **{
            "funding_source": funding_source,
            "function": fn_name,
            **test,
            "mocks": [],
            "skip": funding_source.skip,
        }
    )
    if "mocks" in test:
        if fs_name not in test["mocks"]:
            t.skip = True
            return [t]

        return _tests_from_fs_mocks(t, fn, test, fs_name)

    return [t]


def _tests_from_fs_mocks(t: WalletTest, fn, test, fs_name: str) -> List[WalletTest]:
    tests: List[WalletTest] = []

    fs_mocks = fn["mocks"][fs_name]
    test_mocks = test["mocks"][fs_name]

    for mock_name in fs_mocks:
        tests += _tests_from_mocks(t, fs_mocks[mock_name], test_mocks[mock_name])
    return tests


def _tests_from_mocks(t: WalletTest, fs_mock, test_mocks) -> List[WalletTest]:
    tests: List[WalletTest] = []
    for test_mock in test_mocks:
        # different mocks that result in the same
        # return value for the tested function
        unique_test = _test_from_mocks(t, fs_mock, test_mock)

        tests.append(unique_test)
    return tests


def _test_from_mocks(t: WalletTest, fs_mock, test_mock) -> WalletTest:
    mock = Mock.combine_mocks(fs_mock, test_mock)

    return WalletTest(
        **(
            t.dict()
            | {
                "description": f"""{t.description}:{mock.description or ""}""",
                "mocks": t.mocks + [mock],
                "skip": t.skip or mock.skip,
            }
        )
    )


def build_test_id(test: WalletTest):
    return f"{test.funding_source}.{test.function}({test.description})"


def load_funding_source(funding_source: FundingSourceConfig) -> BaseWallet:
    custom_settings = funding_source.settings
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


async def check_assertions(wallet, _test_data: WalletTest):
    test_data = _test_data.dict()
    tested_func = _test_data.function
    call_params = _test_data.call_params

    if "expect" in test_data:
        await _assert_data(wallet, tested_func, call_params, _test_data.expect)
        # if len(_test_data.mocks) == 0:
        #     # all calls should fail after this method is called
        #     await wallet.cleanup()
        #     # same behaviour expected is server canot be reached
        #     # or if the connection was closed
        #     await _assert_data(wallet, tested_func, call_params, _test_data.expect)
    elif "expect_error" in test_data:
        await _assert_error(wallet, tested_func, call_params, _test_data.expect_error)
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
