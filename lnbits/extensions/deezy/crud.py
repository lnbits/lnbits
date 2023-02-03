from typing import List, Optional

from . import db
from .models import BtcToLnSwap, LnToBtcSwap, Token, UpdateLnToBtcSwap


async def get_ln_to_btc() -> List[LnToBtcSwap]:

    rows = await db.fetchall(
        "SELECT * FROM deezy.ln_to_btc_swap ORDER BY created_at DESC",
    )

    return [LnToBtcSwap(**row) for row in rows]


async def get_btc_to_ln() -> List[BtcToLnSwap]:

    rows = await db.fetchall(
        "SELECT * FROM deezy.btc_to_ln_swap ORDER BY created_at DESC",
    )

    return [BtcToLnSwap(**row) for row in rows]


async def get_token() -> Optional[Token]:

    row = await db.fetchone(
        "SELECT * FROM deezy.token ORDER BY created_at DESC",
    )

    return Token(**row) if row else None


async def save_token(
    data: Token,
) -> Token:

    await db.execute(
        """
        INSERT INTO deezy.token (
            deezy_token
        )
        VALUES (?)
        """,
        (data.deezy_token,),
    )
    return data


async def save_ln_to_btc(
    data: LnToBtcSwap,
) -> LnToBtcSwap:

    return await db.execute(
        """
        INSERT INTO deezy.ln_to_btc_swap (
            amount_sats,
            on_chain_address,
            on_chain_sats_per_vbyte,
            bolt11_invoice,
            fee_sats,
            txid,
            tx_hex
        )
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            data.amount_sats,
            data.on_chain_address,
            data.on_chain_sats_per_vbyte,
            data.bolt11_invoice,
            data.fee_sats,
            data.txid,
            data.tx_hex,
        ),
    )


async def update_ln_to_btc(data: UpdateLnToBtcSwap) -> str:
    await db.execute(
        """
        UPDATE deezy.ln_to_btc_swap
        SET txid = ?, tx_hex = ?
        WHERE bolt11_invoice = ?
        """,
        (data.txid, data.tx_hex, data.bolt11_invoice),
    )

    return data.txid


async def save_btc_to_ln(
    data: BtcToLnSwap,
) -> BtcToLnSwap:

    return await db.execute(
        """
        INSERT INTO deezy.btc_to_ln_swap (
            ln_address,
            on_chain_address,
            secret_access_key,
            commitment,
            signature
        )
        VALUES (?,?,?,?,?)
        """,
        (
            data.ln_address,
            data.on_chain_address,
            data.secret_access_key,
            data.commitment,
            data.signature,
        ),
    )
