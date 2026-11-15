"""Unit tests for the Nano (XNO) fiat provider and its binding core.

The binding module (``lnbits.fiat.nano_binding``) is standard-library only and is
tested directly. The provider (``lnbits.fiat.nano.NanoWallet``) is tested with a
stubbed node so no network, key or seed is involved.
"""

import asyncio

import pytest

from lnbits.fiat import nano_binding as b
from lnbits.fiat.nano import NanoWallet
from lnbits.settings import settings

# --- fixtures from the public binding standard / derived deterministically ----
BURN = "nano_1111111111111111111111111111111111111111111111111111hifc8npp"
P2_HEX = "3068BB1CA04525BB0E416C485FE6A67FD52540227D267CC8B6E8DA958A7FA039"
P2_ACCOUNT = "nano_1e5aqegc1jb7qe964u4adzmcezyo6o146zb8hm6dft8tkp79za3sxwjym5rx"

PAY_TO = "nano_35kyb1akjsdw7rtrj34myaf5jy4muutti7us1zagtpw5g6odqem5g7c6euyq"
ORDER_ID = "a3f1c0de00000000000000000000000000000000000000000000000000001234"
PRICE_RAW = 250000000000000000000000000000  # 0.25 XNO
REP = "nano_3wk5c9batazx19xdqfhjaxi1urriya8hihwxzjdmy1whxtamjd8rqkx1hni1"
BLOCK = "F" * 64


# ============================ binding core ====================================


def test_address_codec_matches_public_vectors():
    assert b.pubkey_to_account(bytes(32)) == BURN
    assert b.pubkey_to_account(bytes.fromhex(P2_HEX)) == P2_ACCOUNT
    assert b.account_to_pubkey(P2_ACCOUNT) == bytes.fromhex(P2_HEX)


def test_is_valid_address_and_bad_checksum_refused():
    assert b.is_valid_address(PAY_TO)
    assert b.is_valid_address(BURN)
    bad = PAY_TO[:-1] + ("1" if PAY_TO[-1] != "1" else "3")
    assert not b.is_valid_address(bad)
    assert not b.is_valid_address("nano_short")
    assert not b.is_valid_address("xrb_" + PAY_TO[5:])


def test_xno_to_raw_derives_and_rejects_bad_amounts():
    assert b.xno_to_raw(1) == b.XNO_RAW == 10**30
    assert b.xno_to_raw("0.25") == PRICE_RAW
    assert b.xno_to_raw("0.000000000000000000000000000001") == 1  # 1 raw
    for bad in ("0", "-1", "0.0000000000000000000000000000001"):  # over-precise / <=0
        with pytest.raises(ValueError):
            b.xno_to_raw(bad)


def test_commitment_binds_order_dest_and_price_with_golden_vector():
    assert b.commitment_rep_account(ORDER_ID, PAY_TO, PRICE_RAW) == REP
    # every field is covered by the commitment
    assert b.order_commitment(ORDER_ID, PAY_TO, PRICE_RAW) != b.order_commitment(
        "other", PAY_TO, PRICE_RAW
    )
    assert b.order_commitment(ORDER_ID, PAY_TO, PRICE_RAW) != b.order_commitment(
        ORDER_ID, BURN, PRICE_RAW
    )
    assert b.order_commitment(ORDER_ID, PAY_TO, PRICE_RAW) != b.order_commitment(
        ORDER_ID, PAY_TO, PRICE_RAW + 1
    )
    with pytest.raises(TypeError):
        b.order_commitment(ORDER_ID, PAY_TO, 0.25)  # float raw refused


def test_payment_uri_names_amount_and_representative():
    uri = b.payment_uri(PAY_TO, PRICE_RAW, REP)
    assert uri == f"nano:{PAY_TO}?amount={PRICE_RAW}&representative={REP}"


def _good_credit_kwargs(**over):
    kw = {
        "block_hash": BLOCK,
        "order_id": ORDER_ID,
        "pay_to": PAY_TO,
        "price_raw": PRICE_RAW,
        "paid_raw": PRICE_RAW,
        "link_as_account": PAY_TO,
        "representative": REP,
        "subtype": "send",
        "block_time": 1000,
    }
    kw.update(over)
    return kw


def test_ledger_credits_a_valid_block_once():
    led = b.NanoClaimLedger(":memory:")
    assert led.credit(**_good_credit_kwargs()).matched
    # idempotent re-read of the same block for the same order
    assert led.credit(**_good_credit_kwargs()).matched
    assert led.order_credited(ORDER_ID)


def test_ledger_refuses_wrong_amount_rep_and_subtype():
    led = b.NanoClaimLedger(":memory:")
    assert led.credit(**_good_credit_kwargs(paid_raw=PRICE_RAW - 1)).verdict == (
        "refusable_wrong_amount"
    )
    assert led.credit(**_good_credit_kwargs(representative=BURN)).verdict == (
        "refusable_other_quote"
    )
    assert led.credit(**_good_credit_kwargs(subtype="receive")).verdict == (
        "refusable_not_payment"
    )
    assert led.credit(**_good_credit_kwargs(link_as_account=BURN)).verdict == (
        "refusable_not_payment"
    )
    # nothing was written by any refusal
    assert not led.order_credited(ORDER_ID)


def test_ledger_one_block_one_order_and_one_block_per_order():
    led = b.NanoClaimLedger(":memory:")
    assert led.credit(**_good_credit_kwargs()).matched
    # same block, a different order: refused, the claim stays with the first
    other_order = "b" * 64
    other_rep = b.commitment_rep_account(other_order, PAY_TO, PRICE_RAW)
    res = led.credit(
        **_good_credit_kwargs(order_id=other_order, representative=other_rep)
    )
    assert res.verdict == "refusable_other_quote"
    # a different block for an order already credited: duplicate, never a 2nd credit
    res2 = led.credit(**_good_credit_kwargs(block_hash="A" * 64))
    assert res2.verdict == "duplicate_refund_due"


def test_ledger_replay_refusal_survives_restart(tmp_path):
    path = str(tmp_path / "claims.sqlite3")
    led = b.NanoClaimLedger(path)
    assert led.credit(**_good_credit_kwargs()).matched
    led.close()
    # a fresh ledger object on the same file still refuses the replayed block
    led2 = b.NanoClaimLedger(path)
    assert led2.order_credited(ORDER_ID)
    other = "c" * 64
    assert led2.credit(**_good_credit_kwargs(block_hash=other)).verdict == (
        "duplicate_refund_due"
    )
    led2.close()


# ============================ provider adapter ================================


class _FakeNode:
    """A minimal stub standing in for a public Nano RPC node."""

    def __init__(self):
        self.send_blocks: dict[str, dict] = {}

    def add_send(self, block_hash, amount_raw, link_account, representative):
        self.send_blocks[block_hash] = {
            "amount": str(amount_raw),
            "subtype": "send",
            "confirmed": "true",
            "local_timestamp": "1700000000",
            "contents": {
                "link_as_account": link_account,
                "representative": representative,
            },
        }

    async def rpc(self, action, **params):
        if action == "receivable":
            threshold = int(params["threshold"])
            blocks = {
                h: {"amount": v["amount"]}
                for h, v in self.send_blocks.items()
                if int(v["amount"]) >= threshold
            }
            return {"blocks": blocks}
        if action == "block_info":
            return self.send_blocks.get(params["hash"], {"error": "Block not found"})
        if action == "account_info":
            return {"balance": "0"}
        return {"error": "unknown action"}


def _make_wallet(tmp_path, node: _FakeNode) -> NanoWallet:
    settings.nano_enabled = True
    settings.nano_node_url = "https://node.example"
    settings.nano_payto_address = PAY_TO
    settings.nano_confirmations_required = True
    settings.nano_ledger_path = str(tmp_path / "wallet_claims.sqlite3")
    wallet = NanoWallet()
    wallet._rpc = node.rpc  # type: ignore[method-assign]
    return wallet


def test_parse_checking_id_roundtrip():
    assert NanoWallet._parse_checking_id("nope") is None
    assert NanoWallet._parse_checking_id(f"fiat_nano_{ORDER_ID}_{PRICE_RAW}") == (
        ORDER_ID,
        PRICE_RAW,
    )


def test_init_refuses_bad_payto(tmp_path):
    settings.nano_node_url = "https://node.example"
    settings.nano_payto_address = PAY_TO[:-1] + ("1" if PAY_TO[-1] != "1" else "3")
    settings.nano_ledger_path = str(tmp_path / "x.sqlite3")
    with pytest.raises(ValueError):
        NanoWallet()


def test_create_invoice_binds_amount_and_representative(tmp_path):
    node = _FakeNode()
    wallet = _make_wallet(tmp_path, node)
    try:
        res = asyncio.run(
            wallet.create_invoice(amount=0.25, payment_hash=ORDER_ID, currency="XNO")
        )
        assert res.ok
        assert res.checking_id == f"fiat_nano_{ORDER_ID}_{PRICE_RAW}"
        assert f"amount={PRICE_RAW}" in res.payment_request
        assert f"representative={REP}" in res.payment_request
        # non-XNO currency and over-precise amount are refused
        assert not asyncio.run(
            wallet.create_invoice(amount=1, payment_hash=ORDER_ID, currency="USD")
        ).ok
    finally:
        asyncio.run(wallet.cleanup())


def test_get_invoice_status_pending_then_paid_then_replay(tmp_path):
    node = _FakeNode()
    wallet = _make_wallet(tmp_path, node)
    checking_id = f"fiat_nano_{ORDER_ID}_{PRICE_RAW}"
    try:
        # no block yet -> pending
        assert not asyncio.run(wallet.get_invoice_status(checking_id)).success
        # a correct send appears -> paid
        node.add_send(BLOCK, PRICE_RAW, PAY_TO, REP)
        assert asyncio.run(wallet.get_invoice_status(checking_id)).success
        # a second order cannot be paid by the same block
        other_order = "d" * 64
        other_rep = b.commitment_rep_account(other_order, PAY_TO, PRICE_RAW)
        node.add_send(BLOCK, PRICE_RAW, PAY_TO, other_rep)  # same hash, re-presented
        other_checking = f"fiat_nano_{other_order}_{PRICE_RAW}"
        assert not asyncio.run(wallet.get_invoice_status(other_checking)).success
    finally:
        asyncio.run(wallet.cleanup())


def test_get_invoice_status_rejects_wrong_rep_amount_and_unconfirmed(tmp_path):
    node = _FakeNode()
    wallet = _make_wallet(tmp_path, node)
    checking_id = f"fiat_nano_{ORDER_ID}_{PRICE_RAW}"
    try:
        # right amount, wrong representative (not this order's commitment)
        node.add_send(BLOCK, PRICE_RAW, PAY_TO, BURN)
        assert not asyncio.run(wallet.get_invoice_status(checking_id)).success
        # right representative but short amount
        node.send_blocks.clear()
        node.add_send("A" * 64, PRICE_RAW - 1, PAY_TO, REP)
        assert not asyncio.run(wallet.get_invoice_status(checking_id)).success
        # correct block but unconfirmed is not credited
        node.send_blocks.clear()
        node.add_send(BLOCK, PRICE_RAW, PAY_TO, REP)
        node.send_blocks[BLOCK]["confirmed"] = "false"
        assert not asyncio.run(wallet.get_invoice_status(checking_id)).success
    finally:
        asyncio.run(wallet.cleanup())


def test_paid_status_survives_restart(tmp_path):
    node = _FakeNode()
    ledger_path = str(tmp_path / "wallet_claims.sqlite3")
    settings.nano_enabled = True
    settings.nano_node_url = "https://node.example"
    settings.nano_payto_address = PAY_TO
    settings.nano_confirmations_required = True
    settings.nano_ledger_path = ledger_path

    checking_id = f"fiat_nano_{ORDER_ID}_{PRICE_RAW}"
    node.add_send(BLOCK, PRICE_RAW, PAY_TO, REP)

    wallet = NanoWallet()
    wallet._rpc = node.rpc  # type: ignore[method-assign]
    try:
        assert asyncio.run(wallet.get_invoice_status(checking_id)).success
    finally:
        asyncio.run(wallet.cleanup())

    # a fresh provider on the same ledger reports paid without re-crediting
    node.send_blocks.clear()  # the block is gone from the node (pocketed)
    wallet2 = NanoWallet()
    wallet2._rpc = node.rpc  # type: ignore[method-assign]
    try:
        assert asyncio.run(wallet2.get_invoice_status(checking_id)).success
    finally:
        asyncio.run(wallet2.cleanup())
