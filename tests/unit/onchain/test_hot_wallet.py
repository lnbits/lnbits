import base64
import json
from typing import Literal

import pytest

from lnbits.onchain.bindings import wally
from lnbits.onchain.helpers import (
    descriptor_fingerprint,
    descriptor_script,
    parse_key,
    script_address,
)
from lnbits.onchain.hot_wallet import (
    HotWalletPayment,
    decrypt_mnemonic,
    encrypt_mnemonic,
    new_mnemonic,
    sign_payment,
    wallet_descriptor,
)
from lnbits.onchain.models import CreatePsbt, WalletAccount

PHRASE = "abandon " * 11 + "about"


@pytest.fixture(autouse=True)
def test_encryption_key(monkeypatch):
    monkeypatch.setenv(
        "WATCHONLY_MASTER_KEY", base64.b64encode(bytes(range(32))).decode()
    )


def wallet_and_payment(network: Literal["Mainnet", "Testnet", "Testnet4"] = "Testnet4"):
    descriptor, _ = wallet_descriptor(PHRASE, network)
    parsed, _ = parse_key(descriptor)
    wallet = WalletAccount(
        id="wallet",
        wallet_id="owner",
        masterpub=descriptor,
        fingerprint=descriptor_fingerprint(parsed),
        title="Server wallet",
        address_no=-1,
        balance=0,
        network=network,
        wallet_kind="hot",
        backup_confirmed=True,
    )
    net = (
        wally.WALLY_NETWORK_BITCOIN_MAINNET
        if network == "Mainnet"
        else wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    previous = wally.tx_init(2, 0, 1, 1)
    wally.tx_add_raw_input(previous, bytes(32), 0, 0xFFFFFFFF, None, None, 0)
    wally.tx_add_raw_output(previous, 100000, descriptor_script(parsed, 0, 0), 0)
    tx = CreatePsbt.parse_obj(
        {
            "masterpubs": [],
            "fee_rate": 1,
            "tx_size": 141,
            "inputs": [
                {
                    "tx_id": bytes(wally.tx_get_txid(previous))[::-1].hex(),
                    "vout": 0,
                    "amount": 100000,
                    "address": script_address(descriptor_script(parsed), net),
                    "branch_index": 0,
                    "address_index": 0,
                    "wallet": "wallet",
                    "tx_hex": wally.tx_to_hex(previous, 0),
                }
            ],
            "outputs": [
                {
                    "amount": 40000,
                    "address": script_address(descriptor_script(parsed, 1, 0), net),
                },
                {
                    "amount": 59000,
                    "address": script_address(descriptor_script(parsed, 0, 1), net),
                    "wallet": "wallet",
                    "branch_index": 1,
                    "address_index": 0,
                },
            ],
        }
    )
    return wallet, HotWalletPayment(transaction=tx, max_fee_sat=1000)


def test_bip84_recovery_vector():
    descriptor, path = wallet_descriptor(PHRASE, "Mainnet")
    parsed, _ = parse_key(descriptor)
    assert path == "m/84'/0'/0'"
    assert (
        script_address(descriptor_script(parsed), wally.WALLY_NETWORK_BITCOIN_MAINNET)
        == "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
    )
    assert new_mnemonic("  " + PHRASE.upper() + "  ") == PHRASE
    with pytest.raises(ValueError):
        new_mnemonic("abandon " * 12)
    assert len(new_mnemonic().split()) == 24


def test_encryption_is_random_authenticated_and_bound_to_wallet(monkeypatch):
    wallet, _ = wallet_and_payment()
    first = encrypt_mnemonic(PHRASE, wallet)
    assert first != encrypt_mnemonic(PHRASE, wallet)
    assert PHRASE not in first
    assert decrypt_mnemonic(first, wallet) == PHRASE
    for field, value in [
        ("id", "other"),
        ("wallet_id", "attacker"),
        ("network", "Mainnet"),
        ("masterpub", "other"),
    ]:
        with pytest.raises(ValueError):
            decrypt_mnemonic(first, wallet.copy(update={field: value}))
    raw = bytearray(base64.b64decode(first))
    raw[-1] ^= 1
    with pytest.raises(ValueError):
        decrypt_mnemonic(base64.b64encode(raw).decode(), wallet)
    monkeypatch.setenv("WATCHONLY_MASTER_KEY", base64.b64encode(bytes(32)).decode())
    with pytest.raises(ValueError):
        decrypt_mnemonic(first, wallet)


@pytest.mark.parametrize("network", ["Mainnet", "Testnet", "Testnet4"])
def test_signs_and_finalizes_native_segwit(network):
    wallet, payment = wallet_and_payment(network)
    result = sign_payment(wallet, encrypt_mnemonic(PHRASE, wallet), payment)
    assert result.tx_hex and result.tx_json
    tx = wally.tx_from_hex(result.tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS)
    assert wally.tx_get_num_inputs(tx) == 1
    assert wally.tx_get_num_outputs(tx) == 2
    assert json.loads(result.tx_json)["fee"] == 1000


@pytest.mark.parametrize(
    "attack",
    [
        "foreign-input",
        "duplicate",
        "amount",
        "outpoint",
        "change-address",
        "foreign-change",
        "network",
        "fee",
        "dust",
        "backup",
    ],
)
def test_signing_rejects_invalid_spending(attack):  # noqa: C901
    wallet, payment = wallet_and_payment()
    tx = payment.transaction
    if attack == "foreign-input":
        tx.inputs[0].wallet = "victim"
    if attack == "duplicate":
        tx.inputs.append(tx.inputs[0].copy())
    if attack == "amount":
        tx.inputs[0].amount += 1000
    if attack == "outpoint":
        tx.inputs[0].vout = 1
    if attack == "change-address":
        tx.outputs[1].address = tx.outputs[0].address
    if attack == "foreign-change":
        tx.outputs[1].wallet = "victim"
    if attack == "network":
        tx.outputs[0].address = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
    if attack == "fee":
        payment.max_fee_sat = 999
    if attack == "dust":
        tx.outputs[0].amount = 1
    if attack == "backup":
        wallet.backup_confirmed = False
    with pytest.raises(ValueError):
        sign_payment(wallet, encrypt_mnemonic(PHRASE, wallet), payment)


def test_fractional_amounts_are_not_truncated():
    _, payment = wallet_and_payment()
    data = payment.dict()
    data["transaction"]["outputs"][0]["amount"] = 1234.5
    with pytest.raises(ValueError, match="whole satoshis"):
        HotWalletPayment(**data)
