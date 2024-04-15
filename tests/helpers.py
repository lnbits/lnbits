import hashlib
import json
import os
import random
import string
import time
from subprocess import PIPE, Popen, TimeoutExpired
from typing import Optional, Tuple

from loguru import logger
from psycopg2 import connect
from psycopg2.errors import InvalidCatalogName

from lnbits import core
from lnbits.db import DB_TYPE, POSTGRES, FromRowModel
from lnbits.wallets import get_funding_source, set_funding_source


class DbTestModel(FromRowModel):
    id: int
    name: str
    value: Optional[str] = None


def get_random_string(iterations: int = 10):
    return "".join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(iterations)
    )


async def get_random_invoice_data():
    return {"out": False, "amount": 10, "memo": f"test_memo_{get_random_string(10)}"}


set_funding_source()
funding_source = get_funding_source()
is_fake: bool = funding_source.__class__.__name__ == "FakeWallet"
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
