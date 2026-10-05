import base64
import json
from typing import Literal

import pytest
from Cryptodome.Cipher import AES

from lnbits.core.models.onchain import CreatePsbt, HotWalletPayment
from lnbits.core.models.wallets import NewHotWallet, OnchainMeta, OnchainWallet
from lnbits.core.services.onchain import (
    decrypt_wallet_mnemonic,
    encrypt_wallet_mnemonic,
    sign_payment,
)
from lnbits.utils.onchain import (
    descriptor_fingerprint,
    descriptor_script,
    new_mnemonic,
    parse_key,
    script_address,
    wallet_descriptor,
    wally,
)

PHRASE = "abandon " * 11 + "about"


@pytest.fixture(autouse=True)
def test_encryption_key(monkeypatch):
    monkeypatch.setenv(
        "WATCHONLY_MASTER_KEY", base64.b64encode(bytes(range(32))).decode()
    )


def wallet_and_payment(
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Testnet4",
    script_type: str = "p2wpkh",
    account_path: str | None = None,
):
    descriptor, path = wallet_descriptor(PHRASE, network, script_type, account_path)
    parsed, _ = parse_key(descriptor)
    wallet = OnchainWallet(
        id="wallet",
        user="owner",
        adminkey="admin-key",
        inkey="invoice-key",
        name="Hot Wallet",
        onchain_network=network,
        onchain_wallet_kind="hot",
        onchain_meta=OnchainMeta(
            backup_confirmed=True,
            masterpub=descriptor,
            fingerprint=descriptor_fingerprint(parsed),
            script_type=script_type,
            accountPath=path,
        ),
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


@pytest.mark.parametrize(
    "script_type,purpose,address",
    [
        ("p2pkh", 44, "1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA"),
        ("p2sh", 49, "37VucYSaXLCAsxYyAPfbSi9eh4iEcbShgf"),
        (
            "p2tr",
            86,
            "bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr",
        ),
    ],
)
def test_hot_wallet_address_types(script_type, purpose, address):
    descriptor, path = wallet_descriptor(PHRASE, "Mainnet", script_type)
    parsed, _ = parse_key(descriptor)
    assert path == f"m/{purpose}'/0'/0'"
    assert (
        script_address(descriptor_script(parsed), wally.WALLY_NETWORK_BITCOIN_MAINNET)
        == address
    )


@pytest.mark.parametrize(
    "path,expected",
    [
        (None, None),
        ("m/84'/0'/7'", "m/84'/0'/7'"),
        (" m/084h/0H/007' ", "m/84'/0'/7'"),
        ("m/0'", "m/0'"),
        ("m/100'/7/3'", "m/100'/7/3'"),
        ("m/2147483647'", "m/2147483647'"),
    ],
)
def test_custom_account_path_validation(path, expected):
    data = NewHotWallet(title="Custom", account_path=path)
    assert data.account_path == expected


@pytest.mark.parametrize(
    "path",
    [
        "",
        "m",
        "84'/0'/0'",
        "m/84'/0'/-1'",
        "m/84'/0'/2147483648'",
        "m/84'/0'/0'/0/0",
        "m/84'/0'/0'/1",
        "m/84'/0'/0'/*",
        "m/84'/0'/0'/<0;1>/*",
        "m/84'/0'/0'/",
        "m/84'//0'",
        "m/84'/0'/one'",
        "m/84'/0'/1.5'",
        "m" + "/0'" * 254,
    ],
)
def test_invalid_custom_account_paths(path):
    with pytest.raises(ValueError):
        NewHotWallet(title="Custom", account_path=path)


def test_encryption_is_random_authenticated_and_bound_to_wallet(monkeypatch):
    wallet, _ = wallet_and_payment()
    first = encrypt_wallet_mnemonic(PHRASE, wallet)
    assert first != encrypt_wallet_mnemonic(PHRASE, wallet)
    assert PHRASE not in first
    assert decrypt_wallet_mnemonic(first, wallet) == PHRASE
    for field, value in [
        ("id", "other"),
        ("onchain_network", "Mainnet"),
        ("onchain_meta", wallet.onchain_meta.copy(update={"masterpub": "other"})),
    ]:
        with pytest.raises(ValueError):
            decrypt_wallet_mnemonic(first, wallet.copy(update={field: value}))
    # Existing wallets used the same ID in both context positions.
    raw = bytearray(base64.b64decode(first))
    old_cipher = AES.new(bytes(range(32)), AES.MODE_GCM, nonce=bytes(raw[1:13]))
    old_cipher.update(
        json.dumps(
            [
                "onchain-v1",
                "wallet",
                "wallet",
                "Testnet4",
                wallet.onchain_meta.masterpub,
            ],
            separators=(",", ":"),
        ).encode()
    )
    assert (
        old_cipher.decrypt_and_verify(bytes(raw[29:]), bytes(raw[13:29])).decode()
        == PHRASE
    )
    raw[-1] ^= 1
    with pytest.raises(ValueError):
        decrypt_wallet_mnemonic(base64.b64encode(raw).decode(), wallet)
    monkeypatch.setenv("WATCHONLY_MASTER_KEY", base64.b64encode(bytes(32)).decode())
    with pytest.raises(ValueError):
        decrypt_wallet_mnemonic(first, wallet)


@pytest.mark.parametrize("network", ["Mainnet", "Testnet", "Testnet4"])
@pytest.mark.parametrize("script_type", ["p2pkh", "p2sh", "p2wpkh", "p2tr"])
@pytest.mark.parametrize("account_path", [None, "m/100'/7/3'"])
def test_signs_and_finalizes_hot_wallet(network, script_type, account_path):
    wallet, payment = wallet_and_payment(network, script_type, account_path)
    result = sign_payment(wallet, encrypt_wallet_mnemonic(PHRASE, wallet), payment)
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
        wallet.onchain_meta.backup_confirmed = False
    with pytest.raises(ValueError):
        sign_payment(wallet, encrypt_wallet_mnemonic(PHRASE, wallet), payment)


def test_fractional_amounts_are_not_truncated():
    _, payment = wallet_and_payment()
    data = payment.dict()
    data["transaction"]["outputs"][0]["amount"] = 1234.5
    with pytest.raises(ValueError, match="whole satoshis"):
        HotWalletPayment(**data)
