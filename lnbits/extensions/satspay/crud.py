import json
from typing import List, Optional

from loguru import logger

from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.helpers import urlsafe_short_hash

from ..watchonly.crud import get_config, get_fresh_address
from . import db
from .helpers import fetch_onchain_balance
from .models import Charges, CreateCharge, SatsPaySettings

###############CHARGES##########################


async def create_charge(user: str, data: CreateCharge) -> Charges:
    charge_id = urlsafe_short_hash()
    if data.onchainwallet:
        config = await get_config(user)
        data.extra = json.dumps(
            {"mempool_endpoint": config.mempool_endpoint, "network": config.network}
        )
        onchain = await get_fresh_address(data.onchainwallet)
        onchainaddress = onchain.address
    else:
        onchainaddress = None
    if data.lnbitswallet:
        payment_hash, payment_request = await create_invoice(
            wallet_id=data.lnbitswallet,
            amount=data.amount,
            memo=charge_id,
            extra={"tag": "charge"},
        )
    else:
        payment_hash = None
        payment_request = None
    await db.execute(
        """
        INSERT INTO satspay.charges (
            id,
            "user",
            description,
            onchainwallet,
            onchainaddress,
            lnbitswallet,
            payment_request,
            payment_hash,
            webhook,
            completelink,
            completelinktext,
            time,
            amount,
            balance,
            extra
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            charge_id,
            user,
            data.description,
            data.onchainwallet,
            onchainaddress,
            data.lnbitswallet,
            payment_request,
            payment_hash,
            data.webhook,
            data.completelink,
            data.completelinktext,
            data.time,
            data.amount,
            0,
            data.extra,
        ),
    )
    return await get_charge(charge_id)


async def update_charge(charge_id: str, **kwargs) -> Optional[Charges]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE satspay.charges SET {q} WHERE id = ?", (*kwargs.values(), charge_id)
    )
    row = await db.fetchone("SELECT * FROM satspay.charges WHERE id = ?", (charge_id,))
    return Charges.from_row(row) if row else None


async def get_charge(charge_id: str) -> Charges:
    row = await db.fetchone("SELECT * FROM satspay.charges WHERE id = ?", (charge_id,))
    return Charges.from_row(row) if row else None


async def get_charges(user: str) -> List[Charges]:
    rows = await db.fetchall(
        """SELECT * FROM satspay.charges WHERE "user" = ? ORDER BY "timestamp" DESC """,
        (user,),
    )
    return [Charges.from_row(row) for row in rows]


async def delete_charge(charge_id: str) -> None:
    await db.execute("DELETE FROM satspay.charges WHERE id = ?", (charge_id,))


async def check_address_balance(charge_id: str) -> Optional[Charges]:
    charge = await get_charge(charge_id)

    if not charge.paid:
        if charge.onchainaddress:
            try:
                respAmount = await fetch_onchain_balance(charge)
                if respAmount > charge.balance:
                    await update_charge(charge_id=charge_id, balance=respAmount)
            except Exception as e:
                logger.warning(e)
        if charge.lnbitswallet:
            invoice_status = await api_payment(charge.payment_hash)

            if invoice_status["paid"]:
                return await update_charge(charge_id=charge_id, balance=charge.amount)
    return await get_charge(charge_id)


################## SETTINGS ###################
async def save_settings(user_id: str, data: SatsPaySettings):
    # insert or update
    row = await db.fetchone(
        """SELECT user_id FROM satspay.settings WHERE user_id = ?""", (user_id,)
    )
    if row:
        await db.execute(
            """
            UPDATE satspay.settings SET custom_css = ? WHERE user_id = ?
            """,
            (data.custom_css, user_id),
        )
    else:
        await db.execute(
            """
            INSERT INTO satspay.settings (
                user_id,
                custom_css
                )
            VALUES (?, ?)
            """,
            (
                user_id,
                data.custom_css,
            ),
        )
    return True


async def get_settings(user_id: str) -> SatsPaySettings:
    row = await db.fetchone(
        """SELECT * FROM satspay.settings WHERE user_id = ?""",
        (user_id,),
    )
    if row:
        return SatsPaySettings.from_row(row)
    else:
        return None
