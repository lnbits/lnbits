import json
from typing import Dict, List, Optional, Union

from pydantic import BaseModel


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
