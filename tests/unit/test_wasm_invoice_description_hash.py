import hashlib

import pytest
from bolt11 import decode
from pydantic import ValidationError

from lnbits.core.crud import create_wallet
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import (
    CreateInvoicePublicRequest,
    CreateInvoiceRequest,
)
from lnbits.core.wasm_ext.storage.crud import OWNER_ID_FIELD
from lnbits.helpers import sha256s
from tests.unit.test_wasm_invoice_security import _payment, _wallet

METADATA = '[["text/plain","Pay to alice"],["text/identifier","alice@example.com"]]'
METADATA_HEX = METADATA.encode().hex()
METADATA_HASH = hashlib.sha256(METADATA.encode()).hexdigest()


@pytest.mark.anyio
async def test_authenticated_invoice_forwards_description_hash(mocker):
    wallet = _wallet()
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", mocker.AsyncMock(return_value=wallet)
    )
    create = mocker.patch(
        "lnbits.core.services.payments.create_payment_request",
        mocker.AsyncMock(return_value=_payment("tips")),
    )
    api = ExtensionHostAPI("tips", ["wallet.create_invoice"], user_id=wallet.user)
    await api.wallet_create_invoice(
        CreateInvoiceRequest(
            wallet_id=wallet.id,
            tag="tips",
            amount=21,
            memo="Tip",
            unhashed_description=METADATA_HEX,
        )
    )
    invoice = create.await_args.args[1]
    assert invoice.unhashed_description == METADATA_HEX
    assert invoice.description_hash is None


@pytest.mark.anyio
async def test_public_invoice_forwards_description_hash(mocker):
    wallet = _wallet()
    row = {"wallet_id": wallet.id, OWNER_ID_FIELD: sha256s(wallet.user)}
    mocker.patch(
        "lnbits.core.wasm_ext.api.host.storage_get_public_row",
        mocker.AsyncMock(return_value=row),
    )
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet", mocker.AsyncMock(return_value=wallet)
    )
    create = mocker.patch(
        "lnbits.core.services.payments.create_payment_request",
        mocker.AsyncMock(return_value=_payment("tips")),
    )
    api = ExtensionHostAPI(
        "tips",
        [
            {
                "id": "wallet.create_invoice_public",
                "policies": [{"table": "links", "wallet_field": "wallet_id"}],
            }
        ],
    )
    await api.wallet_create_invoice_public(
        CreateInvoicePublicRequest(
            source_id="row-1",
            amount=21,
            currency="sat",
            description_hash=METADATA_HASH.upper(),
        )
    )
    invoice = create.await_args.args[1]
    assert invoice.description_hash == METADATA_HASH
    assert invoice.unhashed_description is None


@pytest.mark.parametrize(
    "field, value",
    [
        ("description_hash", "zz" * 32),
        ("description_hash", "ab" * 31),
        ("description_hash", "ab" * 33),
        ("unhashed_description", "abc"),
        ("unhashed_description", "not hex"),
        ("unhashed_description", "ab" * 8193),
    ],
)
def test_invoice_requests_reject_invalid_description_hash(field, value):
    _assert_both_requests_reject({field: value})


def test_invoice_requests_reject_both_description_fields():
    _assert_both_requests_reject(
        {"description_hash": METADATA_HASH, "unhashed_description": METADATA_HEX}
    )


def _assert_both_requests_reject(fields):
    with pytest.raises(ValidationError):
        CreateInvoiceRequest(
            wallet_id="wallet-1", tag="tips", amount=1, memo="", **fields
        )
    with pytest.raises(ValidationError):
        CreateInvoicePublicRequest(
            source_id="row-1", amount=1, currency="sat", **fields
        )


@pytest.mark.anyio
async def test_wasm_invoice_commits_to_unhashed_description(app, from_user):
    wallet = await create_wallet(user_id=from_user.id)
    api = ExtensionHostAPI("tips", ["wallet.create_invoice"], user_id=from_user.id)
    response = await api.wallet_create_invoice(
        CreateInvoiceRequest(
            wallet_id=wallet.id,
            tag="tips",
            amount=21,
            memo="ignored",
            unhashed_description=METADATA_HEX,
        )
    )
    invoice = decode(response.payment_request)
    assert invoice.description_hash == METADATA_HASH
    assert invoice.description is None
