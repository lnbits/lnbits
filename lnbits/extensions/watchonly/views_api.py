import json
from http import HTTPStatus

import httpx
from embit import finalizer, script
from embit.ec import PublicKey
from embit.psbt import PSBT, DerivationPath
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from fastapi import Query, Request
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.watchonly import watchonly_ext

from .crud import (
    create_config,
    create_fresh_addresses,
    create_watch_wallet,
    delete_addresses_for_wallet,
    delete_watch_wallet,
    get_addresses,
    get_config,
    get_fresh_address,
    get_watch_wallet,
    get_watch_wallets,
    update_address,
    update_config,
    update_watch_wallet,
)
from .helpers import parse_key
from .models import (
    BroadcastTransaction,
    Config,
    CreatePsbt,
    CreateWallet,
    ExtractPsbt,
    SignedTransaction,
    WalletAccount,
)

###################WALLETS#############################


@watchonly_ext.get("/api/v1/wallet")
async def api_wallets_retrieve(
    network: str = Query("Mainnet"), wallet: WalletTypeInfo = Depends(get_key_type)
):

    try:
        return [
            wallet.dict()
            for wallet in await get_watch_wallets(wallet.wallet.user, network)
        ]
    except:
        return []


@watchonly_ext.get("/api/v1/wallet/{wallet_id}")
async def api_wallet_retrieve(
    wallet_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    w_wallet = await get_watch_wallet(wallet_id)

    if not w_wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    return w_wallet.dict()


@watchonly_ext.post("/api/v1/wallet")
async def api_wallet_create_or_update(
    data: CreateWallet, w: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        (descriptor, network) = parse_key(data.masterpub)
        if data.network != network["name"]:
            raise ValueError(
                "Account network error.  This account is for '{}'".format(
                    network["name"]
                )
            )

        new_wallet = WalletAccount(
            id="none",
            user=w.wallet.user,
            masterpub=data.masterpub,
            fingerprint=descriptor.keys[0].fingerprint.hex(),
            type=descriptor.scriptpubkey_type(),
            title=data.title,
            address_no=-1,  # so fresh address on empty wallet can get address with index 0
            balance=0,
            network=network["name"],
        )

        wallets = await get_watch_wallets(w.wallet.user, network["name"])
        existing_wallet = next(
            (
                ew
                for ew in wallets
                if ew.fingerprint == new_wallet.fingerprint
                and ew.network == new_wallet.network
                and ew.masterpub == new_wallet.masterpub
            ),
            None,
        )
        if existing_wallet:
            raise ValueError(
                "Account '{}' has the same master pulic key".format(
                    existing_wallet.title
                )
            )

        wallet = await create_watch_wallet(new_wallet)

        await api_get_addresses(wallet.id, w)
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

    config = await get_config(w.wallet.user)
    if not config:
        await create_config(user=w.wallet.user)
    return wallet.dict()


@watchonly_ext.delete("/api/v1/wallet/{wallet_id}")
async def api_wallet_delete(wallet_id, w: WalletTypeInfo = Depends(require_admin_key)):
    wallet = await get_watch_wallet(wallet_id)

    if not wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    await delete_watch_wallet(wallet_id)
    await delete_addresses_for_wallet(wallet_id)

    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


#############################ADDRESSES##########################


@watchonly_ext.get("/api/v1/address/{wallet_id}")
async def api_fresh_address(wallet_id, w: WalletTypeInfo = Depends(get_key_type)):
    address = await get_fresh_address(wallet_id)
    return address.dict()


@watchonly_ext.put("/api/v1/address/{id}")
async def api_update_address(
    id: str, req: Request, w: WalletTypeInfo = Depends(require_admin_key)
):
    body = await req.json()
    params = {}
    # amout is only updated if the address has history
    if "amount" in body:
        params["amount"] = int(body["amount"])
        params["has_activity"] = True

    if "note" in body:
        params["note"] = str(body["note"])

    address = await update_address(**params, id=id)

    wallet = (
        await get_watch_wallet(address.wallet)
        if address.branch_index == 0 and address.amount != 0
        else None
    )

    if wallet and wallet.address_no < address.address_index:
        await update_watch_wallet(
            address.wallet, **{"address_no": address.address_index}
        )
    return address


@watchonly_ext.get("/api/v1/addresses/{wallet_id}")
async def api_get_addresses(wallet_id, w: WalletTypeInfo = Depends(get_key_type)):
    wallet = await get_watch_wallet(wallet_id)
    if not wallet:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Wallet does not exist."
        )

    addresses = await get_addresses(wallet_id)
    config = await get_config(w.wallet.user)

    if not addresses:
        await create_fresh_addresses(wallet_id, 0, config.receive_gap_limit)
        await create_fresh_addresses(wallet_id, 0, config.change_gap_limit, True)
        addresses = await get_addresses(wallet_id)

    receive_addresses = list(filter(lambda addr: addr.branch_index == 0, addresses))
    change_addresses = list(filter(lambda addr: addr.branch_index == 1, addresses))

    last_receive_address = list(
        filter(lambda addr: addr.has_activity, receive_addresses)
    )[-1:]
    last_change_address = list(
        filter(lambda addr: addr.has_activity, change_addresses)
    )[-1:]

    if last_receive_address:
        current_index = receive_addresses[-1].address_index
        address_index = last_receive_address[0].address_index
        await create_fresh_addresses(
            wallet_id, current_index + 1, address_index + config.receive_gap_limit + 1
        )

    if last_change_address:
        current_index = change_addresses[-1].address_index
        address_index = last_change_address[0].address_index
        await create_fresh_addresses(
            wallet_id,
            current_index + 1,
            address_index + config.change_gap_limit + 1,
            True,
        )

    addresses = await get_addresses(wallet_id)
    return [address.dict() for address in addresses]


#############################PSBT##########################


@watchonly_ext.post("/api/v1/psbt")
async def api_psbt_create(
    data: CreatePsbt, w: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        vin = [
            TransactionInput(bytes.fromhex(inp.tx_id), inp.vout) for inp in data.inputs
        ]
        vout = [
            TransactionOutput(out.amount, script.address_to_scriptpubkey(out.address))
            for out in data.outputs
        ]

        descriptors = {}
        for _, masterpub in enumerate(data.masterpubs):
            descriptors[masterpub.id] = parse_key(masterpub.public_key)

        inputs_extra = []

        for i, inp in enumerate(data.inputs):
            bip32_derivations = {}
            descriptor = descriptors[inp.wallet][0]
            d = descriptor.derive(inp.address_index, inp.branch_index)
            for k in d.keys:
                bip32_derivations[PublicKey.parse(k.sec())] = DerivationPath(
                    k.origin.fingerprint, k.origin.derivation
                )
            inputs_extra.append(
                {
                    "bip32_derivations": bip32_derivations,
                    "non_witness_utxo": Transaction.from_string(inp.tx_hex),
                }
            )

        tx = Transaction(vin=vin, vout=vout)
        psbt = PSBT(tx)

        for i, inp in enumerate(inputs_extra):
            psbt.inputs[i].bip32_derivations = inp["bip32_derivations"]
            psbt.inputs[i].non_witness_utxo = inp.get("non_witness_utxo", None)
            print("### ", inp.get("non_witness_utxo", None))

        outputs_extra = []
        bip32_derivations = {}
        for i, out in enumerate(data.outputs):
            if out.branch_index == 1:
                descriptor = descriptors[out.wallet][0]
                d = descriptor.derive(out.address_index, out.branch_index)
                for k in d.keys:
                    bip32_derivations[PublicKey.parse(k.sec())] = DerivationPath(
                        k.origin.fingerprint, k.origin.derivation
                    )
                outputs_extra.append({"bip32_derivations": bip32_derivations})

        for i, out in enumerate(outputs_extra):
            psbt.outputs[i].bip32_derivations = out["bip32_derivations"]

        return psbt.to_string()

    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))


@watchonly_ext.put("/api/v1/psbt/extract")
async def api_psbt_extract_tx(
    data: ExtractPsbt, w: WalletTypeInfo = Depends(require_admin_key)
):
    res = SignedTransaction()
    try:
        psbt = PSBT.from_base64(data.psbtBase64)
        for i, inp in enumerate(data.inputs):
            psbt.inputs[i].non_witness_utxo = Transaction.from_string(inp.tx_hex)

        final_psbt = finalizer.finalize_psbt(psbt)
        if not final_psbt:
            raise ValueError("PSBT cannot be finalized!")
        res.tx_hex = final_psbt.to_string()

        transaction = Transaction.from_string(res.tx_hex)
        tx = {
            "locktime": transaction.locktime,
            "version": transaction.version,
            "outputs": [],
            "fee": psbt.fee(),
        }

        for out in transaction.vout:
            tx["outputs"].append(
                {"amount": out.value, "address": out.script_pubkey.address()}
            )
        res.tx_json = json.dumps(tx)
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    return res.dict()


@watchonly_ext.post("/api/v1/tx")
async def api_tx_broadcast(
    data: BroadcastTransaction, w: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        config = await get_config(w.wallet.user)
        if not config:
            raise ValueError(
                "Cannot broadcast transaction. Mempool endpoint not defined!"
            )

        endpoint = (
            config.mempool_endpoint
            if config.network == "Mainnet"
            else config.mempool_endpoint + "/testnet"
        )
        async with httpx.AsyncClient() as client:
            r = await client.post(endpoint + "/api/tx", data=data.tx_hex)
            tx_id = r.text
            print("### broadcast tx_id: ", tx_id)
            return tx_id
        # return "0f0f0f0f0f0f0f0f0f0f0f00f0f0f0f0f0f0f0f0f0f00f0f0f0f0f0f0.mock.transaction.id"
    except Exception as e:
        print("### broadcast error: ", str(e))
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))


#############################CONFIG##########################


@watchonly_ext.put("/api/v1/config")
async def api_update_config(
    data: Config, w: WalletTypeInfo = Depends(require_admin_key)
):
    config = await update_config(data, user=w.wallet.user)
    return config.dict()


@watchonly_ext.get("/api/v1/config")
async def api_get_config(w: WalletTypeInfo = Depends(get_key_type)):
    config = await get_config(w.wallet.user)
    if not config:
        config = await create_config(user=w.wallet.user)
    return config.dict()
