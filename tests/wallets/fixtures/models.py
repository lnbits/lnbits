from typing import Dict, List, Optional, Union

from pydantic import BaseModel


class FundingSourceConfig(BaseModel):
    name: str
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

    @staticmethod
    def tests_for_funding_source(
        fs: FundingSourceConfig,
        fn_name: str,
        fn,
        test,
    ) -> List["WalletTest"]:
        t = WalletTest(
            **{
                "funding_source": fs,
                "function": fn_name,
                **test,
                "mocks": [],
                "skip": fs.skip,
            }
        )
        if "mocks" in test:
            if fs.name not in test["mocks"]:
                t.skip = True
                return [t]

            return t._tests_from_fs_mocks(fn, test, fs.name)

        return [t]

    def _tests_from_fs_mocks(self, fn, test, fs_name: str) -> List["WalletTest"]:
        tests: List[WalletTest] = []

        fs_mocks = fn["mocks"][fs_name]
        test_mocks = test["mocks"][fs_name]

        for mock_name in fs_mocks:
            tests += self._tests_from_mocks(fs_mocks[mock_name], test_mocks[mock_name])
        return tests

    def _tests_from_mocks(self, fs_mock, test_mocks) -> List["WalletTest"]:
        tests: List[WalletTest] = []
        for test_mock in test_mocks:
            # different mocks that result in the same
            # return value for the tested function
            unique_test = self._test_from_mocks(fs_mock, test_mock)

            tests.append(unique_test)
        return tests

    def _test_from_mocks(self, fs_mock, test_mock) -> "WalletTest":
        mock = Mock.combine_mocks(fs_mock, test_mock)

        return WalletTest(
            **(
                self.dict()
                | {
                    "description": f"""{self.description}:{mock.description or ""}""",
                    "mocks": self.mocks + [mock],
                    "skip": self.skip or mock.skip,
                }
            )
        )


class DataObject:
    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])
