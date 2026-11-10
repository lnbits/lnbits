"""FakeWallet invoices have real BOLT12 encoding and verifiable signatures."""

import hmac
import struct
from hashlib import sha256
from io import BytesIO
from time import time

import pytest
from bech32 import CHARSET, convertbits
from coincurve import PrivateKey, PublicKey, PublicKeyXOnly
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from pyln.proto.message.fundamental_types import (  # type: ignore[import-untyped]
    BigSizeType,
)

from lnbits.utils.bolt12 import _merkle_root
from lnbits.wallets.fake import FakeWallet
from tests.helpers import BOLT12_OFFER_WITH_DESCRIPTION


def read_records(data):
    stream = BytesIO(data)
    records = []
    fields = {}
    while stream.tell() < len(data):
        start = stream.tell()
        field_type = BigSizeType.read(stream)
        size = BigSizeType.read(stream)
        assert field_type is not None and size is not None
        value = stream.read(size)
        assert len(value) == size
        assert not records or field_type > records[-1][0]
        records.append((field_type, data[start : stream.tell()]))
        fields[field_type] = value
    return records, fields


# Official BOLT12 signature-test.json vectors, including a non-power-of-two tree:
# https://github.com/lightning/bolts/blob/master/bolt12/signature-test.json
@pytest.mark.parametrize(
    ("tlv_stream", "merkle"),
    [
        (
            "010203e8",
            "b013756c8fee86503a0b4abdab4cddeb1af5d344ca6fc2fa8b6c08938caa6f93",
        ),
        (
            "010203e802080000010000020003",
            "c3774abbf4815aa54ccaa026bff6581f01f3be5fe814c620a252534f434bc0d1",
        ),
        (
            "010203e80208000001000002000303310266e4598d1d3c415f572a8488830b60"
            "f7e744ed9235eb0b1ba93283b315c0351800000000000000010000000000000002",
            "ab2e79b1283b0b31e0b035258de23782df6b89a38cfa7237bde69aed1a658c5d",
        ),
    ],
)
def test_bolt12_merkle_root_matches_specification(tlv_stream, merkle):
    records, _ = read_records(bytes.fromhex(tlv_stream))
    assert _merkle_root(records).hex() == merkle


@pytest.mark.anyio
@pytest.mark.parametrize("payer_note", [None, "", "  Thanks ☕\n" * 100])
async def test_fake_bolt12_invoice_decodes_and_verifies(payer_note):
    wallet = FakeWallet()
    before = int(time())
    response = await wallet.pay_offer(
        BOLT12_OFFER_WITH_DESCRIPTION,
        fee_limit_msat=100,
        amount_msat=21_000,
        payer_note=payer_note,
    )
    assert response.success and response.payment_request
    assert response.preimage and response.checking_id
    invoice = response.payment_request
    assert invoice.startswith("lni1")
    payload = convertbits([CHARSET.index(c) for c in invoice[4:]], 5, 8, False)
    assert payload is not None
    records, fields = read_records(bytes(payload))
    assert fields[10].decode() == "Test vectors"
    assert fields[18] == b"FakeWallet"
    assert fields[168].hex() == response.checking_id
    assert fields[168] == sha256(bytes.fromhex(response.preimage)).digest()
    assert int.from_bytes(fields[82], "big") == 21_000
    assert int.from_bytes(fields[170], "big") == 21_000
    assert before <= int.from_bytes(fields[164], "big") <= int(time())
    assert len(fields[0]) == 32
    assert PublicKey(fields[88])
    if payer_note:
        assert fields[89].decode() == payer_note
    else:
        assert 89 not in fields

    key = PrivateKey.from_hex(wallet.privkey)
    assert fields[22] == fields[176] == key.public_key.format()
    tag_hash = sha256(b"lightninginvoicesignature").digest()
    digest = sha256(tag_hash * 2 + _merkle_root(records[:-1])).digest()
    assert records[-1][0] == 240
    assert PublicKeyXOnly(fields[176][1:]).verify(fields[240], digest)

    path = BytesIO(fields[160])
    assert path.read(33) == fields[176]
    path_key = path.read(33)
    assert path.read(1) == b"\x01"
    shared_secret = key.ecdh(path_key)
    assert (
        path.read(33)
        == key.public_key.multiply(
            hmac.digest(b"blinded_node_id", shared_secret, "sha256")
        ).format()
    )
    encrypted_size = int.from_bytes(path.read(2), "big")
    encrypted = path.read(encrypted_size)
    assert len(encrypted) == encrypted_size and not path.read()
    recipient_data = ChaCha20Poly1305(
        hmac.digest(b"rho", shared_secret, "sha256")
    ).decrypt(bytes(12), encrypted, b"")
    _, recipient_fields = read_records(recipient_data)
    assert recipient_fields[6] == fields[168]
    assert struct.unpack(">IIHQQH", fields[162]) == (0, 0, 18, 1, (1 << 64) - 1, 0)

    second = await wallet.pay_offer(
        BOLT12_OFFER_WITH_DESCRIPTION, fee_limit_msat=100, amount_msat=21_000
    )
    assert second.success and second.payment_request != invoice
    assert second.checking_id != response.checking_id
