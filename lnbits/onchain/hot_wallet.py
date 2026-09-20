"""Server custody. No private material belongs in wallet models or public metadata."""

import base64
import json
import secrets
from typing import Literal

from Cryptodome.Cipher import AES
from pydantic import BaseModel, Field, validator

from lnbits.core.services.onchain import read_onchain_key

from .bindings import wally
from .helpers import address_script, script_address, transaction_details
from .models import CreatePsbt, MasterPublicKey, SignedTransaction, WalletAccount
from .psbt import create_psbt, finalize_signed_psbt, psbt_fee


class NewHotWallet(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"

    class Config:
        extra = "forbid"


class HotWalletPayment(BaseModel):
    transaction: CreatePsbt
    max_fee_sat: int = Field(..., gt=0, le=10_000_000)

    @validator("transaction", pre=True)
    @classmethod
    def whole_satoshis(cls, value):
        if isinstance(value, dict):
            for item in value.get("inputs", []) + value.get("outputs", []):
                if type(item.get("amount")) is not int:
                    raise ValueError("Amounts must be whole satoshis")
        return value


def encryption_key() -> bytes:
    return read_onchain_key()


def context(wallet: WalletAccount) -> bytes:
    return json.dumps(
        ["onchain-v1", wallet.id, wallet.wallet_id, wallet.network, wallet.masterpub],
        separators=(",", ":"),
    ).encode()


def encrypt_mnemonic(mnemonic: str, wallet: WalletAccount) -> str:
    cipher = AES.new(encryption_key(), AES.MODE_GCM, nonce=secrets.token_bytes(12))
    cipher.update(context(wallet))
    ciphertext, tag = cipher.encrypt_and_digest(mnemonic.encode())
    return base64.b64encode(b"\x01" + cipher.nonce + tag + ciphertext).decode()


def decrypt_mnemonic(encrypted: str, wallet: WalletAccount) -> str:
    raw = base64.b64decode(encrypted, validate=True)
    if len(raw) < 30 or raw[0] != 1:
        raise ValueError("Invalid encrypted wallet")
    cipher = AES.new(encryption_key(), AES.MODE_GCM, nonce=raw[1:13])
    cipher.update(context(wallet))
    return cipher.decrypt_and_verify(raw[29:], raw[13:29]).decode()


def new_mnemonic(supplied: str | None = None) -> str:
    words = wally.bip39_get_wordlist("en")
    if supplied is not None:
        mnemonic = " ".join(supplied.split()).lower()
        wally.bip39_mnemonic_validate(words, mnemonic)
        return mnemonic
    return wally.bip39_mnemonic_from_bytes(words, secrets.token_bytes(32))


def root_key(mnemonic: str, network: str):
    return wally.bip32_key_from_seed(
        wally.bip39_mnemonic_to_seed512(mnemonic, ""),
        (
            wally.BIP32_VER_MAIN_PRIVATE
            if network == "Mainnet"
            else wally.BIP32_VER_TEST_PRIVATE
        ),
        wally.BIP32_FLAG_KEY_PRIVATE,
    )


def wallet_descriptor(mnemonic: str, network: str) -> tuple[str, str]:
    root = root_key(mnemonic, network)
    coin = 0 if network == "Mainnet" else 1
    path = f"84'/{coin}'/0'"
    account = wally.bip32_key_from_parent_path(
        root, [0x80000054, 0x80000000 + coin, 0x80000000], wally.BIP32_FLAG_KEY_PRIVATE
    )
    xpub = wally.bip32_key_to_base58(account, wally.BIP32_FLAG_KEY_PUBLIC)
    fingerprint = bytes(wally.bip32_key_get_fingerprint(root)).hex()
    return f"wpkh([{fingerprint}/{path}]{xpub}/{{0,1}}/*)", f"m/{path}"


def sign_payment(  # noqa: C901
    wallet: WalletAccount, encrypted: str, payment: HotWalletPayment
) -> SignedTransaction:
    data = payment.transaction.copy(deep=True)
    if not wallet.backup_confirmed:
        raise ValueError("Back up this wallet before sending")
    if not 1 <= len(data.inputs) <= 200 or not 1 <= len(data.outputs) <= 100:
        raise ValueError("Invalid number of transaction inputs or outputs")
    seen = set()
    for inp in data.inputs:
        if inp.wallet != wallet.id:
            raise ValueError("Every input must belong to the selected wallet")
        if inp.branch_index not in (0, 1) or not 0 <= inp.address_index < 2**31:
            raise ValueError("Invalid input derivation")
        if (inp.tx_id, inp.vout) in seen:
            raise ValueError("Duplicate transaction input")
        seen.add((inp.tx_id, inp.vout))
        if not 0 < inp.amount <= 2_100_000_000_000_000:
            raise ValueError("Invalid input amount")
    network = (
        wally.WALLY_NETWORK_BITCOIN_MAINNET
        if wallet.network == "Mainnet"
        else wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    for out in data.outputs:
        if not 546 <= out.amount <= 2_100_000_000_000_000:
            raise ValueError("Output is below the minimum or exceeds the supply")
        if (
            script_address(address_script(out.address), network).lower()
            != out.address.lower()
        ):
            raise ValueError("Recipient is on a different network")
        if out.wallet is not None and (
            out.wallet != wallet.id
            or out.branch_index != 1
            or out.address_index is None
            or not 0 <= out.address_index < 2**31
        ):
            raise ValueError("Invalid change output")
    # Never trust public keys supplied by the client to select a private key.
    data.masterpubs = [
        MasterPublicKey(
            id=wallet.id, public_key=wallet.masterpub, fingerprint=wallet.fingerprint
        )
    ]
    psbt = create_psbt(data)
    fee = psbt_fee(psbt)
    if not 0 < fee <= payment.max_fee_sat:
        raise ValueError("Transaction fee exceeds the approved maximum")
    mnemonic = decrypt_mnemonic(encrypted, wallet)
    if wallet_descriptor(mnemonic, wallet.network)[0] != wallet.masterpub:
        raise ValueError("Wallet key does not match its descriptor")
    wally.psbt_sign_bip32(psbt, root_key(mnemonic, wallet.network), 0)
    transaction = finalize_signed_psbt(psbt)
    details = transaction_details(transaction, network)
    details["fee"] = fee
    return SignedTransaction(
        tx_hex=wally.tx_to_hex(transaction, wally.WALLY_TX_FLAG_USE_WITNESS),
        tx_json=json.dumps(details),
    )
