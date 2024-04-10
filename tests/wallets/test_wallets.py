import importlib

import pytest
from mock import Mock
from pytest_mock.plugin import MockerFixture

from lnbits.core.models import BaseWallet
from tests.helpers import (
    FundingSourceConfig,
    WalletTest,
    rest_wallet_fixtures_from_json,
)

wallets_module = importlib.import_module("lnbits.wallets")


class DataObject:
    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])


def build_test_id(test: WalletTest):
    return f"{test.funding_source}.{test.function}({test.description})"


def _raise(error):
    data = error["data"] if "data" in error else None
    if "module" not in error or "class" not in error:
        return Exception(data)

    error_module = importlib.import_module(error["module"])
    error_class = getattr(error_module, error["class"])

    return error_class(**data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_data",
    rest_wallet_fixtures_from_json("tests/wallets/fixture2.json"),
    ids=build_test_id,
)
async def test_wallets(mocker: MockerFixture, test_data: WalletTest):
    if test_data.skip:
        pytest.skip()

    for mock in test_data.mocks:
        return_value = {}
        for field_name in mock.response:
            value = mock.response[field_name]
            values = value if isinstance(value, list) else [value]

            return_value[field_name] = Mock(
                side_effect=[_mock_field(f) for f in values]
            )

        m = _data_mock(return_value)
        mocker.patch(mock.method, m)

    wallet = _load_funding_source(test_data.funding_source)

    expected_calls = _spy_mocks(mocker, test_data, wallet)

    await _check_assertions(wallet, test_data)

    _check_calls(expected_calls)


def _check_calls(expected_calls):
    for func in expected_calls:
        func_calls = expected_calls[func]
        for func_call in func_calls:
            req = func_call["request_data"]
            args = req["args"] if "args" in req else {}
            kwargs = req["kwargs"] if "kwargs" in req else {}
            if "klass" in req:
                *rest, cls = req["klass"].split(".")
                req_module = importlib.import_module(".".join(rest))
                req_class = getattr(req_module, cls)
                func_call["spy"].assert_called_with(req_class(*args, **kwargs))
            else:
                func_call["spy"].assert_called_with(*args, **kwargs)


def _spy_mocks(mocker: MockerFixture, test_data: WalletTest, wallet: BaseWallet):
    expected_calls = {}
    for mock in test_data.mocks:
        for field_name in mock.response:
            value = mock.response[field_name]
            values = value if isinstance(value, list) else [value]

            expected_calls[field_name] = [
                {
                    "spy": mocker.spy(
                        getattr(wallet, test_data.funding_source.client_field),
                        field_name,
                    ),
                    "request_data": f["request_data"],
                }
                for f in values
                if f["request_type"] == "function" and "request_data" in f
            ]

    return expected_calls


def _mock_field(field):
    response_type = field["response_type"]
    request_type = field["request_type"]
    response = field["response"]

    if request_type == "data":
        return _dict_to_object(response)

    if request_type == "function":
        if response_type == "data":
            return _dict_to_object(response)

        if response_type == "exception":
            return _raise(response)

    return response


def _load_funding_source(funding_source: FundingSourceConfig) -> BaseWallet:
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


def _dict_to_object(data: dict) -> DataObject:
    if not data:
        return data
    d = {**data}
    for k in data:
        value = data[k]
        if isinstance(value, dict):
            d[k] = _dict_to_object(value)

    return DataObject(**d)


def _data_mock(data: dict) -> Mock:
    return Mock(return_value=_dict_to_object(data))


async def _check_assertions(wallet, _test_data: WalletTest):
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
