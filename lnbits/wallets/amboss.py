"""Amboss Payments funding source.

Talks to the Amboss Payments GraphQL API (rails) so every invoice and payment is
recorded in the Amboss transaction ledger. Sending is non-custodial: the node's
admin macaroon is fetched encrypted, decrypted in-process with the team password
(Argon2id + NIP-44 v2 — mirroring the @ambosstech/payments TS SDK), and the
payment is executed directly against the node's LND REST endpoint.

`checking_id` is the Amboss transaction id, so status polling reads the ledger
(`transaction.find_one`) rather than the node.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import ssl
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from loguru import logger

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)

# --- crypto: ports of the SDK's argon2 + nip44 (must match byte-for-byte) ------


def _argon2id(password: bytes, salt: bytes) -> bytes:
    # RFC 9106 Argon2id v0x13. Params must match the Amboss Payments backend
    # and the @ambosstech/payments SDK, or the derived key won't decrypt anything.
    return Argon2id(
        salt=salt, length=32, iterations=3, lanes=4, memory_cost=64000
    ).derive(password)


def _derive_master_key(password: str, team_id: str) -> str:
    """Argon2id(password, salt=teamId) -> master key (hex)."""
    salt = team_id.strip().lower().encode()
    return _argon2id(password.strip().encode(), salt).hex()


def create_master_password_hash(password: str, team_id: str) -> tuple[str, str]:
    """Mirror of the Amboss backend's `createMasterPasswordHash`.

    masterKey          = Argon2id(password, salt=teamId)          # hex string
    masterPasswordHash = Argon2id(utf8(masterKey_hex), salt=pw)   # sent to server
    """
    master_key = _derive_master_key(password, team_id)
    master_password_hash = _argon2id(
        master_key.encode(), password.strip().encode()
    ).hex()
    return master_key, master_password_hash


def _nip44_message_keys(
    conversation_key: bytes, nonce: bytes
) -> tuple[bytes, bytes, bytes]:
    keys = HKDFExpand(algorithm=hashes.SHA256(), length=76, info=nonce).derive(
        conversation_key
    )
    return keys[0:32], keys[32:44], keys[44:76]


def nip44_decrypt(payload: str, conversation_key_hex: str) -> str:
    """NIP-44 v2 symmetric decrypt (ChaCha20 + HMAC-SHA256), keyed by a 32-byte
    hex key used directly as the conversation key (no ECDH)."""
    conversation_key = bytes.fromhex(conversation_key_hex)
    data = base64.b64decode(payload)
    if not data or data[0] != 2:
        raise ValueError("unsupported nip44 payload version")
    nonce, ciphertext, mac = data[1:33], data[33:-32], data[-32:]

    chacha_key, chacha_nonce, hmac_key = _nip44_message_keys(conversation_key, nonce)
    calc_mac = hmac.new(hmac_key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(calc_mac, mac):
        raise ValueError("nip44 mac mismatch (wrong key/password)")

    # cryptography's ChaCha20 nonce = 4-byte LE counter (0) + 12-byte nonce.
    full_nonce = (0).to_bytes(4, "little") + chacha_nonce
    decryptor = Cipher(
        algorithms.ChaCha20(chacha_key, full_nonce), mode=None
    ).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    plaintext_len = int.from_bytes(padded[:2], "big")
    return padded[2 : 2 + plaintext_len].decode("utf-8")


def _normalize_macaroon_hex(value: str) -> str:
    """Macaroon may come back as hex or base64; LND wants hex."""
    stripped = value.strip()
    if len(stripped) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in stripped):
        return stripped.lower()
    return base64.b64decode(stripped).hex()


# --- GraphQL documents (only the fields this wallet uses) ----------------------

_TX_FIELDS = "id status payment_hash payment_request fee amount_sats"

_CREATE_RECEIVE = f"""
mutation($input: CreateReceiveTransactionInput!) {{
  payment {{ transaction {{ create_receive(input: $input) {{ {_TX_FIELDS} }} }} }}
}}"""

_CREATE_SEND = f"""
mutation($input: CreateSendTransactionInput!) {{
  payment {{ transaction {{ create_send(input: $input) {{ {_TX_FIELDS} }} }} }}
}}"""

_GET_TRANSACTION = f"""
query($id: String!) {{
  payment {{ transaction {{ find_one(id: $id) {{ {_TX_FIELDS} }} }} }}
}}"""

_GET_WALLET_BALANCE = """
query($id: String!) {
  payment { wallet { find_one(id: $id) { id balance { balance } } } }
}"""

_GET_SEND_CONTEXT = """
query($id: String!) {
  payment {
    id
    wallet { find_one(id: $id) { id environment { type } } }
  }
}"""

_GET_NODE_PERMISSIONS = """
query($id: String!, $password_hash: String) {
  payment { wallet { find_one(id: $id) {
    id
    asset { type }
    node_permissions(password_hash: $password_hash) {
      encrypted_symmetric_key
      nodes { encrypted_macaroon tls_cert sockets { lnd { rest } litd { rest } } }
    }
  } } }
}"""

_FIND_BY_PAYMENT_HASH = f"""
query($hash: String!) {{
  payment {{
    transaction {{
      find_one(lightning: {{ payment_hash: $hash }}) {{ {_TX_FIELDS} }}
    }}
  }}
}}"""


class AmbossWallet(Wallet):
    """https://github.com/AmbossTech/sdk/tree/main/packages/payments"""

    def __init__(self):
        super().__init__()
        if not settings.amboss_service_api_key:
            raise ValueError(
                "cannot initialize AmbossWallet: missing amboss_service_api_key"
            )
        if not settings.amboss_wallet_id:
            raise ValueError("cannot initialize AmbossWallet: missing amboss_wallet_id")

        self.wallet_id = settings.amboss_wallet_id
        self.team_password = settings.amboss_team_password
        self.endpoint = settings.amboss_api_endpoint
        self.sandbox = settings.amboss_sandbox
        self.sandbox_auto_complete = settings.amboss_sandbox_auto_complete
        # Static per wallet: (team_id, is_sandbox, node, macaroon_hex). Cached so
        # repeat sends skip the ~3s GetSendContext + Argon2 + node-permissions
        # decrypt. If the node or macaroon rotates, restart to pick up the change.
        self._send_cache: tuple[str, bool, dict | None, str | None] | None = None

        self.client = httpx.AsyncClient(
            base_url=self.endpoint,
            headers={
                "x-api-key": settings.amboss_service_api_key,
                "Content-Type": "application/json",
                "User-Agent": settings.user_agent,
            },
        )

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as exc:
            logger.warning(f"Error closing wallet connection: {exc}")

    async def _gql(self, query: str, variables: dict) -> dict:
        r = await self.client.post(
            "", json={"query": query, "variables": variables}, timeout=40
        )
        # GraphQL errors (including schema-validation failures) come back as a
        # JSON `errors` array even on HTTP 400 — surface that before falling
        # back to raise_for_status, otherwise the real reason is lost.
        try:
            body = r.json()
        except ValueError:
            r.raise_for_status()
            raise
        if body.get("errors"):
            raise ValueError(str(body["errors"][0].get("message", body["errors"])))
        r.raise_for_status()
        return body["data"]

    async def status(self) -> StatusResponse:
        try:
            data = await self._gql(_GET_WALLET_BALANCE, {"id": self.wallet_id})
            wallet = data["payment"]["wallet"]["find_one"]
            # balance is in the wallet asset's base unit. This wallet only
            # supports BASE_ASSET (BTC) wallets, so that unit is sats.
            return StatusResponse(None, int(wallet["balance"]["balance"]) * 1000)
        except Exception as exc:
            logger.warning(exc)
            return StatusResponse(f"Unable to connect to {self.endpoint}.", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        _input: dict[str, Any] = {"wallet_id": self.wallet_id, "amount": str(amount)}
        # `description` is just a label stored on the transaction row, so it's
        # sent unconditionally. `bolt11.description_hash` is a separate, wire-
        # level concept (LNURL-pay/LUD-06 requires it to equal
        # sha256(metadata)); the Amboss backend drops the invoice's 'd' tag
        # when it's set (BOLT11 allows only one of 'd'/'h'), independent of
        # this transaction's stored description.
        if memo:
            _input["description"] = memo
        hash_hex = (
            description_hash.hex()
            if description_hash
            else hashlib.sha256(unhashed_description).hexdigest()
            if unhashed_description
            else None
        )
        if hash_hex:
            _input["bolt11"] = {"description_hash": hash_hex}
        if kwargs.get("expiry"):
            _input["expires_in_seconds"] = int(kwargs["expiry"])
        if self.sandbox and self.sandbox_auto_complete:
            # rails only acts on this for SANDBOX wallets; harmless otherwise.
            _input["metadata"] = json.dumps({"amb_sandbox_behavior": "complete"})

        try:
            data = await self._gql(_CREATE_RECEIVE, {"input": _input})
            tx = data["payment"]["transaction"]["create_receive"]
        except Exception as exc:
            logger.warning(exc)
            return InvoiceResponse(ok=False, error_message=str(exc))

        checking_id = tx["id"]
        self.pending_invoices.append(checking_id)
        return InvoiceResponse(
            ok=True,
            checking_id=checking_id,
            payment_request=tx["payment_request"],
        )

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            _team_id, is_sandbox, node, macaroon_hex = await self._send_context()
            send_input: dict[str, Any] = {
                "wallet_id": self.wallet_id,
                "request": {"bolt11": bolt11},
            }
            if self.sandbox and self.sandbox_auto_complete:
                # rails only acts on this for SANDBOX wallets; harmless otherwise.
                send_input["metadata"] = json.dumps(
                    {"amb_sandbox_behavior": "complete"}
                )
            tx = (await self._gql(_CREATE_SEND, {"input": send_input}))["payment"][
                "transaction"
            ]["create_send"]
        except Exception as exc:
            logger.warning(f"AmbossWallet send error: {exc}")
            return PaymentResponse(error_message=str(exc))

        # lnbits keys outgoing payments by the bolt11 payment_hash and fails the
        # payment unless pay_invoice returns the same checking_id, so use the
        # hash create_send recorded (equals the bolt11 hash), not the tx id.
        checking_id = (tx.get("payment_hash") or "").lower()
        if is_sandbox:
            # No node to pay; backend settles asynchronously — poll the ledger.
            return PaymentResponse(ok=None, checking_id=checking_id)

        assert node is not None and macaroon_hex is not None  # set in non-sandbox path
        payment_request = tx.get("payment_request") or bolt11
        return await self._pay_via_node(
            node, macaroon_hex, payment_request, fee_limit_msat, checking_id
        )

    async def _send_context(self) -> tuple[str, bool, dict | None, str | None]:
        """Resolve (and cache) the static send context for this wallet: the team
        id (Argon2 salt), sandbox flag, and — for live wallets — the LND node and
        its decrypted admin macaroon."""
        if self._send_cache is not None:
            return self._send_cache

        payment = (await self._gql(_GET_SEND_CONTEXT, {"id": self.wallet_id}))[
            "payment"
        ]
        # payment.id is the team id — the Argon2 salt for macaroon decryption.
        team_id = payment["id"]
        is_sandbox = payment["wallet"]["find_one"]["environment"]["type"] == "SANDBOX"

        node = macaroon_hex = None
        if not is_sandbox:
            if not self.team_password:
                raise ValueError("amboss_team_password required to send")
            node, macaroon_hex = await self._resolve_node(team_id)

        self._send_cache = (team_id, is_sandbox, node, macaroon_hex)
        return self._send_cache

    async def _resolve_node(self, team_id: str) -> tuple[dict, str]:
        master_key, master_password_hash = create_master_password_hash(
            self.team_password, team_id
        )
        wallet = (
            await self._gql(
                _GET_NODE_PERMISSIONS,
                {"id": self.wallet_id, "password_hash": master_password_hash},
            )
        )["payment"]["wallet"]["find_one"]

        if wallet["asset"]["type"] != "BASE_ASSET":
            raise ValueError("AmbossWallet only supports BASE_ASSET (BTC) wallets")

        perms = wallet["node_permissions"]
        node = next(
            (
                n
                for n in perms["nodes"]
                if n["sockets"].get("lnd") and n["sockets"]["lnd"]["rest"]
            ),
            None,
        )
        if not node:
            raise ValueError("no LND REST endpoint available for this wallet")

        symmetric_key = nip44_decrypt(perms["encrypted_symmetric_key"], master_key)
        macaroon = nip44_decrypt(node["encrypted_macaroon"], symmetric_key)
        return node, _normalize_macaroon_hex(macaroon)

    async def _pay_via_node(
        self,
        node: dict,
        macaroon_hex: str,
        payment_request: str,
        fee_limit_msat: int,
        checking_id: str,
    ) -> PaymentResponse:
        rest_host = node["sockets"]["lnd"]["rest"]
        tls_cert = node.get("tls_cert")
        verify: Any = ssl.create_default_context(cadata=tls_cert) if tls_cert else True

        req = {
            "payment_request": payment_request,
            "fee_limit_msat": fee_limit_msat,
            "timeout_seconds": 30,
            "no_inflight_updates": True,
        }
        try:
            async with httpx.AsyncClient(
                base_url=rest_host,
                headers={"Grpc-Metadata-macaroon": macaroon_hex},
                verify=verify,
            ) as node_client:
                r = await node_client.post("/v2/router/send", json=req, timeout=None)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            logger.warning(f"AmbossWallet node pay error: {exc}")
            # Payment may still be in flight on the node; leave it pending.
            return PaymentResponse(ok=None, checking_id=checking_id)

        payment = data.get("result", data)
        status = payment.get("status")
        if status == "SUCCEEDED":
            return PaymentResponse(
                ok=True,
                checking_id=checking_id,
                fee_msat=abs(int(payment.get("fee_msat", 0))),
                preimage=payment.get("payment_preimage"),
            )
        if status == "FAILED":
            return PaymentResponse(
                ok=False,
                checking_id=checking_id,
                error_message=payment.get("failure_reason", "payment failed"),
            )
        return PaymentResponse(ok=None, checking_id=checking_id)

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        # Invoice checking_id is the Amboss transaction id (UUID).
        try:
            tx = (await self._gql(_GET_TRANSACTION, {"id": checking_id}))["payment"][
                "transaction"
            ]["find_one"]
        except Exception as exc:
            logger.warning(f"AmbossWallet invoice status error: {exc}")
            return PaymentPendingStatus()
        return self._map_tx_status(tx)

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        # Payment checking_id is the bolt11 payment_hash — look it up in the
        # ledger by hash (never via the node, which is used only for paying).
        try:
            tx = (await self._gql(_FIND_BY_PAYMENT_HASH, {"hash": checking_id}))[
                "payment"
            ]["transaction"]["find_one"]
        except Exception as exc:
            # find_one throws "not found" until the send tx is visible — pending.
            logger.warning(f"AmbossWallet payment status error: {exc}")
            return PaymentPendingStatus()
        return self._map_tx_status(tx)

    def _map_tx_status(self, tx: dict | None) -> PaymentStatus:
        if not tx:
            return PaymentPendingStatus()
        status = tx.get("status")
        if status == "COMPLETED":
            fee = tx.get("fee")
            return PaymentSuccessStatus(
                fee_msat=abs(int(fee)) * 1000 if fee is not None else None
            )
        if status in ("FAILED", "EXPIRED"):
            return PaymentFailedStatus()
        return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        # No push channel in the SDK; inherit the base 5s poll over pending_invoices.
        async for checking_id in super().paid_invoices_stream():
            yield checking_id


def _self_check() -> None:
    """Prove the ported crypto reproduces the TS SDK byte-for-byte.

    Run: python -m lnbits.wallets.amboss

    Fixtures below were generated offline by the SDK's own libraries
    (@noble/hashes argon2id, nostr-tools nip44) — see scripts/amboss-fixture.
    They pin the full send-path crypto: argon2 key derivation (both steps, with
    the trim/lower + hex-string-as-password encoding) and the two-step NIP-44
    decrypt chain (masterKey -> symmetricKey -> macaroon).
    """
    # Official NIP-44 v2 vector — proves HKDF/ChaCha nonce order/HMAC/unpad.
    assert (
        nip44_decrypt(
            "AgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABee0G5VSK0/9YypIObAtDKfYEAjD35"
            "uVkHyB0F4DwrcNaCXlCWZKaArsGrY6M9wnuTMxWfp1RTN9Xga8no+kF5Vsb",
            "c41c775356fd92eadc63ff5a0dc1da211b268cbea22316767095b2871ea1412d",
        )
        == "a"
    )

    password, team_id = "CorrectHorseBatteryStaple", "Team-ABCDEF-0123456789"
    enc_symmetric_key = (
        "AtTigMMQNSYlsDcRdrXNse9tiJHerVNQIualUYH+83z57yJLWYLWR6/F1hOR84jPfSvOgCsoq"
        "TWufdGoJMrDoR4cFiF9E+RYKp1gKlu89dJKJA5Sl9IUWvwPrrlKCXnU5nlsIKAn8iFzfnUuAk"
        "IhG/GaGtu7V1wCz68VXSOIIA0l7vg="
    )
    enc_macaroon = (
        "AkpB8MavSNfEH5MvGhVzWUA8kutzu74ETVrjS55Bac2Wcd8gVas2c1mmEYwUM2rVgpme9db1w"
        "ECXVUJFhVarcKDMTJF6P87LlQfjHRg8t9oxoCyIbEcv6C0Dt3V8UFZrAKei5rE7A5z70PXzLc"
        "3H8Lr2m+cilXnBBC6TQzg6YVZpgpA="
    )
    master_key, master_password_hash = create_master_password_hash(password, team_id)
    assert (
        master_key == "1c46299fbd90ea8e026baaaba498e928588c8d371daf3a5c051b5f3a1a5d99c9"
    )
    assert (
        master_password_hash
        == "4fd0954f3dbfb6ced05286d4a0733f92a5bcd7405761bf7d6d31a1259774dbcc"  # noqa: S105
    )
    symmetric_key = nip44_decrypt(enc_symmetric_key, master_key)
    assert (
        symmetric_key
        == "a3f1c9d2b4e6081357092468acebdf01a3f1c9d2b4e6081357092468acebdf01"
    )
    macaroon = nip44_decrypt(enc_macaroon, symmetric_key)
    assert (
        _normalize_macaroon_hex(macaroon)
        == "0201036c6e64025f030a10abababababababababababababababababababab"
    )
    print("amboss crypto self-check OK (matches SDK ground-truth fixtures)")


if __name__ == "__main__":
    _self_check()
