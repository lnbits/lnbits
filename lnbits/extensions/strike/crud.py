from typing import List, Optional

import httpx

from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.helpers import urlsafe_short_hash

# from lnbits.db import open_ext_db
from . import db
from .models import CreateConfiguration, StrikeConfiguration, StrikeForward

############### CONFIGURATIONS ##########################


async def create_configuration(
    data: CreateConfiguration, currency: str
) -> StrikeConfiguration:
    """Create a new Configuration"""
    id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO strike.configurations (
            id,
            lnbits_wallet,
            handle,
            description,
            api_key,
            currency
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (id, data.lnbits_wallet, data.handle, data.description, data.api_key, currency),
    )

    config = await get_configuration(id)
    assert config, "Newly created configuration couldn't be retrieved"
    return config


async def get_configuration(id: str) -> StrikeConfiguration:
    row = await db.fetchone("SELECT * FROM strike.configurations WHERE id = ?", (id,))
    return StrikeConfiguration.from_row(row) if row else None


async def get_configuration_by_wallet(wallet: str) -> StrikeConfiguration:
    row = await db.fetchone(
        "SELECT * FROM strike.configurations WHERE lnbits_wallet = ?", (wallet,)
    )
    return StrikeConfiguration.from_row(row) if row else None


async def get_configurations(wallet_id: str) -> Optional[list]:
    """Return all StrikeConfiguration belonging assigned to the wallet_id"""
    rows = await db.fetchall(
        "SELECT * FROM strike.configurations WHERE lnbits_wallet = ?", (wallet_id,)
    )
    return [StrikeConfiguration(**row) for row in rows] if rows else None


async def delete_configuration(id: int) -> None:
    """Delete a StrikeConfiguration"""
    await db.execute("DELETE FROM strike.configurations WHERE id = ?", (id,))


############### FORWARDS ##########################


async def create_forward(data: StrikeForward) -> StrikeForward:
    """Create a new Forward"""
    id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO strike.forwards (
            id,
            lnbits_wallet,
            handle,
            message,
            currency,
            sats_original,
            msats_fee,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            id,
            data.lnbits_wallet,
            data.handle,
            data.message,
            data.currency,
            data.sats_original,
            data.msats_fee,
            data.amount,
        ),
    )

    config = await get_forward(id)
    assert config, "Newly created forward couldn't be retrieved"
    return config


async def update_forward(forward: StrikeForward) -> StrikeForward:
    id = forward.id
    params = forward.dict()
    del params["id"]
    q = ", ".join([f"{field[0]} = ?" for field in params.items()])
    await db.execute(
        f"UPDATE strike.forwards SET {q} WHERE id = ?", (*params.values(), id)
    )
    config = await get_forward(id)
    assert config, "Updated forward couldn't be retrieved"
    return config


async def get_forward(id: str) -> StrikeForward:
    row = await db.fetchone("SELECT * FROM strike.forwards WHERE id = ?", (id,))
    return StrikeForward.from_row(row) if row else None


async def get_forwards(wallet_id: str) -> Optional[list]:
    """Return all StrikeForwards belonging assigned to the wallet_id"""
    rows = await db.fetchall(
        "SELECT * FROM strike.forwards WHERE lnbits_wallet = ? ORDER BY timestamp DESC",
        (wallet_id,),
    )
    return [StrikeForward(**row) for row in rows] if rows else None
