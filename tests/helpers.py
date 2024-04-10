import hashlib
import json
import os
import random
import string
import time
from subprocess import PIPE, Popen, TimeoutExpired
from typing import Dict, List, Optional, Tuple, Union

from loguru import logger
from psycopg2 import connect
from psycopg2.errors import InvalidCatalogName
from pydantic import BaseModel

from lnbits import core
from lnbits.db import DB_TYPE, POSTGRES, FromRowModel
from lnbits.wallets import get_wallet_class, set_wallet_class


class DbTestModel(FromRowModel):
    id: int
    name: str
    value: Optional[str] = None


def get_random_string(N: int = 10):
    return "".join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(N)
    )


async def get_random_invoice_data():
    return {"out": False, "amount": 10, "memo": f"test_memo_{get_random_string(10)}"}


set_wallet_class()
WALLET = get_wallet_class()
is_fake: bool = WALLET.__class__.__name__ == "FakeWallet"
is_regtest: bool = not is_fake


docker_lightning_cli = [
    "docker",
    "exec",
    "lnbits-lnd-1-1",
    "lncli",
    "--network",
    "regtest",
    "--rpcserver=lnd-1",
]

docker_bitcoin_cli = [
    "docker",
    "exec",
    "lnbits-bitcoind-1-1" "bitcoin-cli",
    "-rpcuser=lnbits",
    "-rpcpassword=lnbits",
    "-regtest",
]


docker_lightning_unconnected_cli = [
    "docker",
    "exec",
    "lnbits-lnd-2-1",
    "lncli",
    "--network",
    "regtest",
    "--rpcserver=lnd-2",
]


def run_cmd(cmd: list) -> str:
    timeout = 20
    process = Popen(cmd, stdout=PIPE, stderr=PIPE)

    def process_communication(comm):
        stdout, stderr = comm
        output = stdout.decode("utf-8").strip()
        error = stderr.decode("utf-8").strip()
        return output, error

    try:
        now = time.time()
        output, error = process_communication(process.communicate(timeout=timeout))
        took = time.time() - now
        logger.debug(f"ran command output: {output}, error: {error}, took: {took}s")
        return output
    except TimeoutExpired:
        process.kill()
        output, error = process_communication(process.communicate())
        logger.error(f"timeout command: {cmd}, output: {output}, error: {error}")
        raise


def run_cmd_json(cmd: list) -> dict:
    output = run_cmd(cmd)
    try:
        return json.loads(output) if output else {}
    except json.decoder.JSONDecodeError:
        logger.error(f"failed to decode json from cmd `{cmd}`: {output}")
        raise


def get_hold_invoice(sats: int) -> Tuple[str, dict]:
    preimage = os.urandom(32)
    preimage_hash = hashlib.sha256(preimage).hexdigest()
    cmd = docker_lightning_cli.copy()
    cmd.extend(["addholdinvoice", preimage_hash, str(sats)])
    json = run_cmd_json(cmd)
    return preimage.hex(), json


def settle_invoice(preimage: str) -> str:
    cmd = docker_lightning_cli.copy()
    cmd.extend(["settleinvoice", preimage])
    return run_cmd(cmd)


def cancel_invoice(preimage_hash: str) -> str:
    cmd = docker_lightning_cli.copy()
    cmd.extend(["cancelinvoice", preimage_hash])
    return run_cmd(cmd)


def get_real_invoice(sats: int) -> dict:
    cmd = docker_lightning_cli.copy()
    cmd.extend(["addinvoice", str(sats)])
    return run_cmd_json(cmd)


def pay_real_invoice(invoice: str) -> str:
    cmd = docker_lightning_cli.copy()
    cmd.extend(["payinvoice", "--force", invoice])
    return run_cmd(cmd)


def mine_blocks(blocks: int = 1) -> str:
    cmd = docker_bitcoin_cli.copy()
    cmd.extend(["-generate", str(blocks)])
    return run_cmd(cmd)


def get_unconnected_node_uri() -> str:
    cmd = docker_lightning_unconnected_cli.copy()
    cmd.append("getinfo")
    info = run_cmd_json(cmd)
    pubkey = info["identity_pubkey"]
    return f"{pubkey}@lnd-2:9735"


def create_onchain_address(address_type: str = "bech32") -> str:
    cmd = docker_bitcoin_cli.copy()
    cmd.extend(["getnewaddress", address_type])
    return run_cmd(cmd)


def pay_onchain(address: str, sats: int) -> str:
    btc = sats * 0.00000001
    cmd = docker_bitcoin_cli.copy()
    cmd.extend(["sendtoaddress", address, str(btc)])
    return run_cmd(cmd)


def clean_database(settings):
    if DB_TYPE == POSTGRES:
        conn = connect(settings.lnbits_database_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            try:
                cur.execute("DROP DATABASE lnbits_test")
            except InvalidCatalogName:
                pass
            cur.execute("CREATE DATABASE lnbits_test")
        core.db.__init__("database")
        conn.close()
    else:
        # TODO: do this once mock data is removed from test data folder
        # os.remove(settings.lnbits_data_folder + "/database.sqlite3")
        pass


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
                    funding_source = FundingSourceConfig(
                                **funding_sources[fs_name]
                            )
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
