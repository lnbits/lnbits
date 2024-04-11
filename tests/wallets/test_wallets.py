import importlib
from typing import Dict, List, Optional

import pytest
from mock import Mock
from pytest_mock.plugin import MockerFixture

from lnbits.core.models import BaseWallet
from tests.wallets.helpers import (
    DataObject,
    WalletTest,
    build_test_id,
    check_assertions,
    load_funding_source,
    rest_wallet_fixtures_from_json,
)
from tests.wallets.helpers import (
    Mock as RpcMock,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_data",
    rest_wallet_fixtures_from_json("tests/wallets/fixtures_rpc.json"),
    ids=build_test_id,
)
async def test_wallets(mocker: MockerFixture, test_data: WalletTest):
    if test_data.skip:
        pytest.skip()

    for mock in test_data.mocks:
        _apply_rpc_mock(mocker, mock)

    wallet = load_funding_source(test_data.funding_source)

    expected_calls = _spy_mocks(mocker, test_data, wallet)

    await check_assertions(wallet, test_data)

    _check_calls(expected_calls)


def _apply_rpc_mock(mocker: MockerFixture, mock: RpcMock):
    return_value = {}
    assert isinstance(mock.response, dict), "Expected data RPC response"
    for field_name in mock.response:
        value = mock.response[field_name]
        values = value if isinstance(value, list) else [value]

        return_value[field_name] = Mock(side_effect=[_mock_field(f) for f in values])

    m = _data_mock(return_value)
    assert mock.method, "Missing method for RPC mock."
    mocker.patch(mock.method, m)


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
    assert (
        test_data.funding_source.client_field
    ), f"Missing client field for wallet {wallet}"
    client_field = getattr(wallet, test_data.funding_source.client_field)
    expected_calls: Dict[str, List] = {}
    for mock in test_data.mocks:
        spy = _spy_mock(mocker, mock, client_field)
        expected_calls |= spy

    return expected_calls


def _spy_mock(mocker: MockerFixture, mock: RpcMock, client_field):
    expected_calls: Dict[str, List] = {}
    assert isinstance(mock.response, dict), "Expected data RPC response"
    for field_name in mock.response:
        value = mock.response[field_name]
        values = value if isinstance(value, list) else [value]

        expected_calls[field_name] = [
            {
                "spy": mocker.spy(client_field, field_name),
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


def _dict_to_object(data: Optional[dict]) -> Optional[DataObject]:
    if not data:
        return None
    d = {**data}
    for k in data:
        value = data[k]
        if isinstance(value, dict):
            d[k] = _dict_to_object(value)

    return DataObject(**d)


def _data_mock(data: dict) -> Mock:
    return Mock(return_value=_dict_to_object(data))


def _raise(error: dict):
    data = error["data"] if "data" in error else None
    if "module" not in error or "class" not in error:
        return Exception(data)

    error_module = importlib.import_module(error["module"])
    error_class = getattr(error_module, error["class"])

    return error_class(**data)
