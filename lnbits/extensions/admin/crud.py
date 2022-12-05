from typing import Optional

from lnbits.core.crud import create_payment
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import readonly_variables, settings
from lnbits.tasks import internal_invoice_queue

from . import db
from .models import AdminSettings, UpdateSettings


async def update_wallet_balance(wallet_id: str, amount: int):
    internal_id = f"internal_{urlsafe_short_hash()}"

    payment = await create_payment(
        wallet_id=wallet_id,
        checking_id=internal_id,
        payment_request="admin_internal",
        payment_hash="admin_internal",
        amount=amount * 1000,
        memo="Admin top up",
        pending=False,
    )
    # manually send this for now
    await internal_invoice_queue.put(internal_id)

    return payment


async def get_admin_settings() -> AdminSettings:
    row = await db.fetchone("SELECT * FROM admin.settings")
    admin_settings = AdminSettings(**row, lnbits_allowed_funding_sources=settings.lnbits_allowed_funding_sources)
    for key, _ in row.items():
        if hasattr(admin_settings, key):
            setattr(admin_settings, key, getattr(settings, key))
    return admin_settings


async def update_admin_settings(data: UpdateSettings) -> Optional[AdminSettings]:
    fields = []
    for key, value in data.items():
        if not key in readonly_variables:
            setattr(settings, key, value)
            if type(value) == list:
                joined = ",".join(value)
                fields.append(f"{key} = '{joined}'")
            if type(value) == int or type(value) == float:
                fields.append(f"{key} = {value}")
            if type(value) == bool:
                fields.append(f"{key} = {'true' if value else 'false'}")
            if type(value) == str:
                value = value.replace("'", "")
                fields.append(f"{key} = '{value}'")
    q = ", ".join(fields)
    await db.execute(f"UPDATE admin.settings SET {q}")
    row = await db.fetchone("SELECT * FROM admin.settings")
    assert row, "Newly updated settings couldn't be retrieved"
    return AdminSettings(**row) if row else None


async def delete_admin_settings():
    await db.execute("DELETE FROM admin.settings")
