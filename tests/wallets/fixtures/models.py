from typing import Dict, List, Optional, Union

from pydantic import BaseModel


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

    @staticmethod
    def combine_mocks(fs_mock, test_mock):
        _mock = fs_mock | test_mock
        if "response" in _mock and "response" in fs_mock:
            _mock["response"] |= fs_mock["response"]
        return Mock(**_mock)


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
