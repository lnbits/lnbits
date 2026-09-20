import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from lnbits.onchain import views_api
from lnbits.onchain.bindings import wally
from lnbits.onchain.decorators import OnchainAuth
from lnbits.onchain.helpers import (
    address_script,
    descriptor_script,
    parse_key,
    script_address,
)
from lnbits.onchain.models import CreatePsbt, ExtractPsbt, ExtractTx
from lnbits.onchain.psbt import (
    _input_partial_signatures,
    combine_matching_psbt,
    create_psbt,
    finalize_signed_psbt,
    psbt_fee,
)

# Captured before the migration, using only deterministic public test seeds.
VECTORS = json.loads(Path(__file__).with_name("bitcoin_vectors.json").read_text())


@pytest.fixture
def psbt_api_app():
    async def authenticated():
        return None

    app = FastAPI()
    app.include_router(views_api.onchain_api_router, prefix="/watchonly")
    app.dependency_overrides[views_api.require_onchain_admin] = authenticated
    return app


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["psbtBase64", "psbt_base64"])
@pytest.mark.parametrize("kind", ["pkh", "sh", "wpkh", "tr"])
@pytest.mark.parametrize("network", ["Mainnet", "Testnet", "Testnet4"])
async def test_extract_http_accepts_browser_and_python_field_names(
    psbt_api_app, field, kind, network
):
    vector = signing_vector(kind, "main" if network == "Mainnet" else "test")
    async with AsyncClient(
        transport=ASGITransport(app=psbt_api_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/watchonly/api/v1/psbt/extract",
            json={
                field: vector["signed"],
                "inputs": [{"tx_hex": vector["data"]["inputs"][0]["tx_hex"]}],
                "network": network,
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["tx_hex"] == vector["tx_hex"]
    assert json.loads(response.json()["tx_json"])["fee"] == 1000


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"psbtBase64": ""}, {"psbt_base64": ""}])
async def test_extract_http_rejects_missing_or_empty_psbt(psbt_api_app, payload):
    async with AsyncClient(
        transport=ASGITransport(app=psbt_api_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/watchonly/api/v1/psbt/extract", json={**payload, "inputs": []}
        )
    assert response.status_code == 422


def signing_vector(kind="wpkh", network="test"):
    return next(
        v for v in VECTORS["signing"] if v["kind"] == kind and v["network"] == network
    )


def signing_data(kind="wpkh", network="test"):
    root = wally.bip32_key_from_seed(
        bytes(range(32)),
        (
            wally.BIP32_VER_MAIN_PRIVATE
            if network == "main"
            else wally.BIP32_VER_TEST_PRIVATE
        ),
        wally.BIP32_FLAG_KEY_PRIVATE,
    )
    data = CreatePsbt(**signing_vector(kind, network)["data"])
    return root, data.masterpubs[0].public_key, data


@pytest.mark.parametrize("kind", ["pkh", "sh", "wpkh"])
@pytest.mark.parametrize("sighash", [1, 2, 3, 0x81, 0x82, 0x83])
def test_ecdsa_signatures_are_verified_before_finalizing(kind, sighash):
    root, _, data = signing_data(kind)
    psbt = create_psbt(data)
    wally.psbt_set_input_sighash(psbt, 0, sighash)
    wally.psbt_sign_bip32(psbt, root, 0)
    assert finalize_signed_psbt(wally.psbt_clone(psbt, 0))
    pubkey, signature = next(iter(_input_partial_signatures(psbt)[0].items()))
    corrupt = signature[:-2] + bytes([signature[-2] ^ 1, signature[-1]])
    wally.psbt_set_input_signatures(psbt, 0, wally.map_from_dict({pubkey: corrupt}))
    with pytest.raises(ValueError, match="Invalid ECDSA signature"):
        finalize_signed_psbt(psbt)


@pytest.mark.parametrize("kind", ["pkh", "sh", "wpkh", "tr"])
@pytest.mark.parametrize("finalized", [False, True])
def test_matching_psbt_preserves_transaction_and_combines_metadata(kind, finalized):
    vector = signing_vector(kind)
    expected = wally.psbt_from_base64(vector["unsigned"], 0)
    signed = wally.psbt_from_base64(vector["signed"], 0)
    if finalized:
        wally.psbt_finalize(signed, 0)
    combined = combine_matching_psbt(expected, signed)
    tx = finalize_signed_psbt(combined)
    assert wally.tx_to_hex(tx, wally.WALLY_TX_FLAG_USE_WITNESS) == vector["tx_hex"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation", ["amount", "address", "sequence", "outpoint", "version", "locktime"]
)
async def test_extract_rejects_different_reviewed_transaction(psbt_api_app, mutation):
    vector = signing_vector()
    expected = wally.psbt_from_base64(vector["unsigned"], 0)
    raw = bytearray(wally.tx_to_bytes(wally.psbt_get_global_tx(expected), 0))
    # This deterministic vector has one input and two outputs.
    offsets = {
        "version": 0,
        "outpoint": 5,
        "sequence": 42,
        "amount": 47,
        "address": 57,
        "locktime": len(raw) - 4,
    }
    raw[offsets[mutation]] ^= 1
    altered = wally.psbt_init(0, 1, 2, 0, 0)
    wally.psbt_set_global_tx(altered, wally.tx_from_bytes(raw, 0))
    async with AsyncClient(
        transport=ASGITransport(app=psbt_api_app), base_url="http://test"
    ) as client:
        response = await client.put(
            "/watchonly/api/v1/psbt/extract",
            json={
                "psbtBase64": vector["signed"],
                "expectedPsbtBase64": wally.psbt_to_base64(altered, 0),
                "inputs": [],
            },
        )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Signed PSBT does not match the transaction under review"
    )


@pytest.mark.parametrize(
    "vector", VECTORS["signing"], ids=lambda v: f'{v["network"]}-{v["kind"]}'
)
def test_existing_psbt_wire_format_and_signed_transaction(vector):
    psbt = create_psbt(CreatePsbt(**vector["data"]))
    # Includes all input/output origins, script metadata and compact witness UTXOs.
    assert wally.psbt_to_base64(psbt, 0) == vector["unsigned"]
    assert psbt_fee(psbt) == 1000
    signed = wally.psbt_from_base64(vector["signed"], 0)
    tx = finalize_signed_psbt(signed)
    assert wally.tx_to_hex(tx, wally.WALLY_TX_FLAG_USE_WITNESS) == vector["tx_hex"]


@pytest.mark.parametrize("network", ["main", "test"])
@pytest.mark.parametrize("kind", ["pkh", "sh", "wpkh", "tr"])
def test_signing_metadata_and_finalization(kind, network):
    root, _, data = signing_data(kind, network)
    psbt = create_psbt(data)
    assert psbt_fee(psbt) == 1000
    assert bool(wally.psbt_get_input_witness_utxo(psbt, 0)) == (kind != "pkh")
    assert bool(wally.psbt_get_input_utxo(psbt, 0)) == (kind == "pkh")
    assert wally.psbt_get_output_keypaths_size(psbt, 0) == 0
    assert not wally.psbt_get_output_taproot_internal_key(psbt, 0)
    if kind == "tr":
        assert wally.psbt_get_input_taproot_internal_key(psbt, 0)
        assert wally.psbt_get_output_taproot_internal_key(psbt, 1)
        assert wally.psbt_get_input_keypaths_size(psbt, 0) == 0
    else:
        assert wally.psbt_get_output_keypaths_size(psbt, 1) == 1
    wally.psbt_sign_bip32(psbt, root, 0)
    tx = finalize_signed_psbt(psbt)
    assert [wally.tx_get_output_satoshi(tx, i) for i in range(2)] == [40000, 59000]


def test_change_metadata_follows_each_output_after_shuffling():
    _, _, data = signing_data()
    data.outputs.reverse()
    data.outputs.append(data.outputs[0].copy(deep=True))
    psbt = create_psbt(data)
    assert [wally.psbt_get_output_keypaths_size(psbt, i) for i in range(3)] == [1, 0, 1]
    wally.psbt_set_output_keypaths(psbt, 0, wally.map_keypath_bip32_init(0))
    assert wally.psbt_get_output_keypaths_size(psbt, 2) == 1


@pytest.mark.parametrize(
    "field,value",
    [("tx_id", "11" * 32), ("vout", 9), ("amount", 99999), ("address_index", 9)],
)
def test_inconsistent_input_rejected(field, value):
    _, _, data = signing_data()
    setattr(data.inputs[0], field, value)
    with pytest.raises(ValueError, match="Input"):
        create_psbt(data)


def test_inconsistent_change_rejected():
    _, _, data = signing_data()
    data.outputs[1].address_index = 9
    with pytest.raises(ValueError, match="Output"):
        create_psbt(data)


@pytest.mark.parametrize("sighash", [0, 1, 2, 3, 0x81, 0x82, 0x83])
def test_taproot_key_signature_verification(sighash):
    root, _, data = signing_data("tr")
    psbt = create_psbt(data)
    wally.psbt_set_input_sighash(psbt, 0, sighash)
    wally.psbt_sign_bip32(psbt, root, 0)
    signature = bytes(wally.psbt_get_input_taproot_signature(psbt, 0))
    assert len(signature) == (65 if sighash else 64)
    invalid = wally.psbt_clone(psbt, 0)
    wally.psbt_set_input_taproot_signature(
        invalid, 0, bytes([signature[0] ^ 1]) + signature[1:]
    )
    with pytest.raises(ValueError, match="Invalid Taproot"):
        finalize_signed_psbt(invalid)
    assert finalize_signed_psbt(psbt)


def test_unsigned_psbt_cannot_be_finalized():
    _, _, data = signing_data()
    with pytest.raises(ValueError, match="cannot be finalized"):
        finalize_signed_psbt(create_psbt(data))


def test_compact_segwit_psbt_stays_below_bowser_transfer_limit():
    _, _, data = signing_data()
    previous = wally.tx_from_hex(data.inputs[0].tx_hex, 0)
    spk = wally.tx_get_output_script(previous, 0)
    for _ in range(100):
        wally.tx_add_raw_output(previous, data.inputs[0].amount, spk, 0)
    data.inputs[0].tx_hex = wally.tx_to_hex(previous, 0)
    data.inputs[0].tx_id = bytes(wally.tx_get_txid(previous))[::-1].hex()
    data.inputs = [data.inputs[0].copy(update={"vout": i}) for i in range(64)]
    encoded = wally.psbt_to_base64(create_psbt(data), 0)
    assert len(encoded) <= 16384
    assert wally.psbt_get_num_inputs(wally.psbt_from_base64(encoded, 0)) == 64


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["pkh", "sh", "wpkh", "tr"])
@pytest.mark.parametrize("network", ["Mainnet", "Testnet", "Testnet4"])
async def test_psbt_api_create_and_extract(kind, network):
    root, _, data = signing_data(kind, "main" if network == "Mainnet" else "test")
    encoded = await views_api.api_psbt_create(data, _auth=OnchainAuth("test"))
    psbt = wally.psbt_from_base64(encoded, 0)
    wally.psbt_sign_bip32(psbt, root, 0)
    result = await views_api.api_psbt_extract_tx(
        ExtractPsbt.parse_obj(
            {
                "psbt_base64": wally.psbt_to_base64(psbt, 0),
                "inputs": [{"tx_hex": data.inputs[0].tx_hex}],
                "network": network,
            }
        ),
        _auth=OnchainAuth("test"),
    )
    assert (
        wally.tx_get_num_outputs(
            wally.tx_from_hex(result.tx_hex, wally.WALLY_TX_FLAG_USE_WITNESS)
        )
        == 2
    )
    assert result.tx_json and result.tx_hex
    details = json.loads(result.tx_json)
    assert details["fee"] == 1000
    assert details["outputs"] == [
        {"amount": out.amount, "address": out.address} for out in data.outputs
    ]
    raw = await views_api.api_extract_tx(
        ExtractTx(tx_hex=result.tx_hex, network=network), _auth=OnchainAuth("test")
    )
    assert raw["tx_json"] == {k: v for k, v in details.items() if k != "fee"}
    request = SimpleNamespace(json=AsyncMock(return_value={"psbtBase64": encoded}))
    assert await views_api.api_psbt_utxos_tx(
        cast(Request, request), _auth=OnchainAuth("test")
    ) == [{"tx_id": data.inputs[0].tx_id, "vout": 0}]


@pytest.mark.anyio
async def test_extract_rejects_unrelated_previous_transaction():
    vector = signing_vector()
    wrong = signing_vector("pkh")["data"]["inputs"][0]["tx_hex"]
    with pytest.raises(HTTPException, match="outpoint"):
        await views_api.api_psbt_extract_tx(
            ExtractPsbt.parse_obj(
                {"psbt_base64": vector["signed"], "inputs": [{"tx_hex": wrong}]}
            ),
            _auth=OnchainAuth("test"),
        )


@pytest.mark.parametrize("wrapper", ["sh", "wsh", "sh(wsh"])
def test_multisig_metadata_and_signatures(wrapper):
    root, text, data = signing_data()
    second = wally.bip32_key_from_seed(
        bytes(range(1, 33)), wally.BIP32_VER_TEST_PRIVATE, 0
    )
    second_pub = wally.bip32_key_to_base58(second, wally.BIP32_FLAG_KEY_PUBLIC)
    fingerprint = bytes(wally.bip32_key_get_fingerprint(second)).hex()
    first_key = text[5:-1]
    data.masterpubs[0].public_key = (
        f"{wrapper}(sortedmulti(2,{first_key},[{fingerprint}]{second_pub}/{{0,1}}/*)"
        + ")" * (wrapper.count("(") + 1)
    )
    descriptor, _ = parse_key(data.masterpubs[0].public_key)
    address = script_address(
        descriptor_script(descriptor), wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    previous = wally.tx_from_hex(data.inputs[0].tx_hex, 0)
    wally.tx_set_output_script(previous, 0, address_script(address))
    data.inputs[0].tx_hex = wally.tx_to_hex(previous, 0)
    data.inputs[0].tx_id = bytes(wally.tx_get_txid(previous))[::-1].hex()
    data.inputs[0].address = address
    data.outputs[1].address = wally.descriptor_to_address(descriptor, 0, 1, 3, 0)
    psbt = create_psbt(data)
    assert wally.psbt_get_input_keypaths_size(psbt, 0) == 2
    assert bool(wally.psbt_get_input_witness_script(psbt, 0)) == (wrapper != "sh")
    wally.psbt_sign_bip32(psbt, root, 0)
    with pytest.raises(ValueError, match="cannot be finalized"):
        finalize_signed_psbt(wally.psbt_clone(psbt, 0))
    wally.psbt_sign_bip32(psbt, second, 0)
    assert finalize_signed_psbt(psbt)


@pytest.mark.parametrize(
    "kind,prefix,purpose",
    [("pkh", "043587cf", 44), ("sh", "044a5262", 49), ("wpkh", "045f1cf6", 84)],
)
def test_bare_account_key_signing_metadata(kind, prefix, purpose):
    root, text, data = signing_data(kind)
    descriptor, _ = parse_key(text)
    account = wally.descriptor_get_key(descriptor, 0)
    raw = bytes(wally.base58_to_bytes(account, wally.BASE58_FLAG_CHECKSUM))
    data.masterpubs[0].public_key = wally.base58_from_bytes(
        bytes.fromhex(prefix) + raw[4:], wally.BASE58_FLAG_CHECKSUM
    )
    psbt = create_psbt(data)
    account_private = wally.bip32_key_from_parent_path(
        root, [purpose | 2**31, 1 | 2**31, 2**31], 0
    )
    keypath = bytes(wally.psbt_get_input_keypath(psbt, 0, 0))
    assert keypath[:4] == bytes(wally.bip32_key_get_fingerprint(account_private))
    assert keypath[4:] == bytes(8)  # Relative account path /0/0.
    wally.psbt_sign_bip32(psbt, account_private, 0)
    assert finalize_signed_psbt(psbt)


def test_taproot_tree_addresses_preserved_but_signing_rejected():
    _, text, data = signing_data("tr")
    key = text[3:-1]
    data.masterpubs[0].public_key = f"tr({key},{{pk({key}),pk({key})}})"
    descriptor, _ = parse_key(data.masterpubs[0].public_key)
    address = script_address(
        descriptor_script(descriptor), wally.WALLY_NETWORK_BITCOIN_TESTNET
    )
    assert address.startswith("tb1p")
    previous = wally.tx_from_hex(data.inputs[0].tx_hex, 0)
    wally.tx_set_output_script(previous, 0, address_script(address))
    data.inputs[0].tx_hex = wally.tx_to_hex(previous, 0)
    data.inputs[0].tx_id = bytes(wally.tx_get_txid(previous))[::-1].hex()
    with pytest.raises(ValueError, match="Only Taproot key-spend"):
        create_psbt(data)
