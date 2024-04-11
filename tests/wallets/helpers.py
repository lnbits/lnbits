import importlib
import json
from typing import Dict, List, Optional, Union

import pytest
from pydantic import BaseModel

from lnbits.core.models import BaseWallet

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

            for test in fn["tests"]:
                """create an unit test for each funding source"""

                for fs_name in funding_sources:
                    funding_source = FundingSourceConfig(**funding_sources[fs_name])
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
                            tests[fs_name].append(t)
                            continue

                        test_mocks_names = test["mocks"][fs_name]

                        fs_mocks = fn["mocks"][fs_name]
                        for mock_name in fs_mocks:
                            for test_mock in test_mocks_names[mock_name]:
                                # different mocks that result in the same
                                # return value for the tested function
                                _mock = fs_mocks[mock_name] | test_mock
                                if (
                                    "response" in _mock
                                    and "response" in fs_mocks[mock_name]
                                ):
                                    _mock["response"] |= fs_mocks[mock_name]["response"]
                                mock = Mock(**_mock)

                                unique_test = WalletTest(**t.dict())
                                unique_test.description = (
                                    f"""{t.description}:{mock.description or ""}"""
                                )
                                unique_test.mocks = t.mocks + [mock]
                                unique_test.skip = t.skip or mock.skip

                                tests[fs_name].append(unique_test)
                    else:
                        # add the test without mocks
                        tests[fs_name].append(t)

        all_tests = sum([tests[fs_name] for fs_name in tests], [])
        return all_tests


class FundingSourceConfig(BaseModel):
    skip: Optional[bool]
    wallet_class: str
    client_field: Optional[str]
    settings: dict


class FunctionMock(BaseModel):
    uri: Optional[str]
    query_params: Optional[dict]
    headers: Optional[dict]
    method: Optional[str]


class TestMock(BaseModel):
    skip: Optional[bool]
    description: Optional[str]
    request_type: Optional[str]
    request_body: Optional[dict]
    response_type: str
    response: Union[str, dict]


class Mock(FunctionMock, TestMock):
    pass


class FunctionMocks(BaseModel):
    mocks: Dict[str, FunctionMock]


class FunctionTest(BaseModel):
    description: str
    call_params: dict
    expect: dict
    mocks: Dict[str, List[Dict[str, TestMock]]]


class FunctionData(BaseModel):
    """Data required for testing this function"""

    "Function level mocks that apply for all tests of this function"
    mocks: List[FunctionMock] = []

    "All the tests for this function"
    tests: List[FunctionTest] = []


class WalletTest(BaseModel):
    skip: Optional[bool]
    function: str
    description: str
    funding_source: FundingSourceConfig
    call_params: Optional[dict] = {}
    expect: Optional[dict]
    expect_error: Optional[dict]
    mocks: List[Mock] = []


class DataObject:
    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])


def build_test_id(test: WalletTest):
    return f"{test.funding_source}.{test.function}({test.description})"


def load_funding_source(
    funding_source: FundingSourceConfig, custom_settings: Optional[dict] = {}
) -> BaseWallet:
    custom_settings = funding_source.settings | custom_settings
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
