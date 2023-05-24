import hashlib
import json
import random
import secrets
import string
from subprocess import PIPE, Popen, run

from lnbits.core.crud import create_payment
from lnbits.wallets import get_wallet_class, set_wallet_class


async def credit_wallet(wallet_id: str, amount: int):
    preimage = secrets.token_hex(32)
    m = hashlib.sha256()
    m.update(f"{preimage}".encode())
    payment_hash = m.hexdigest()
    await create_payment(
        wallet_id=wallet_id,
        payment_request="",
        payment_hash=payment_hash,
        checking_id=payment_hash,
        preimage=preimage,
        memo=f"funding_test_{get_random_string(5)}",
        amount=amount,  # msat
        pending=False,  # not pending, so it will increase the wallet's balance
    )


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


docker_bitcoin_rpc = "lnbits"
docker_prefix = "lnbits-legend"
docker_cmd = "docker exec"

docker_lightning = f"{docker_cmd} {docker_prefix}-lnd-1-1"
docker_lightning_cli = f"{docker_lightning} lncli --network regtest --rpcserver=lnd-1"

docker_bitcoin = f"{docker_cmd} {docker_prefix}-bitcoind-1-1"
docker_bitcoin_cli = f"{docker_bitcoin} bitcoin-cli -rpcuser={docker_bitcoin_rpc} -rpcpassword={docker_bitcoin_rpc} -regtest"


def run_cmd(cmd: str) -> str:
    return run(cmd, shell=True, capture_output=True).stdout.decode("UTF-8").strip()


def run_cmd_json(cmd: str) -> dict:
    return json.loads(run_cmd(cmd))


def get_real_invoice(sats: int) -> dict:
    return run_cmd_json(f"{docker_lightning_cli} addinvoice {sats}")


def pay_real_invoice(invoice: str) -> Popen:
    return Popen(
        f"{docker_lightning_cli} payinvoice --force {invoice}",
        shell=True,
        stdin=PIPE,
        stdout=PIPE,
    )


def mine_blocks(blocks: int = 1) -> str:
    return run_cmd(f"{docker_bitcoin_cli} -generate {blocks}")


def create_onchain_address(address_type: str = "bech32") -> str:
    return run_cmd(f"{docker_bitcoin_cli} getnewaddress {address_type}")


def pay_onchain(address: str, sats: int) -> str:
    btc = sats * 0.00000001
    return run_cmd(f"{docker_bitcoin_cli} sendtoaddress {address} {btc}")
