from typing import Optional

from lnbits.core.crud import create_account, create_payment
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


async def get_admin_settings() -> Optional[AdminSettings]:
    row = await db.fetchone("SELECT * FROM admin.settings")
    if not row:
        return None
    return AdminSettings(
        lnbits_allowed_funding_sources=settings.lnbits_allowed_funding_sources, **row
    )


async def delete_admin_settings():
    await db.execute("DELETE FROM admin.settings")


async def update_admin_settings(data: UpdateSettings):
    # TODO why are those field here, they are not in UpdateSettings
    # TODO: why is UpdateSettings of type dict here? thats why type:ignore is needed
    data.pop("lnbits_allowed_funding_sources")  # type: ignore
    data.pop("super_user")  # type: ignore
    q, values = get_q_and_values(data)
    await db.execute(f"UPDATE admin.settings SET {q}", (values,))  # type: ignore


def get_q_and_values(data):
    keys = []
    values = []
    for key, value in data.items():
        setattr(settings, key, value)
        keys.append(f"{key} = ?")
        if type(value) == list:
            value = ",".join(value)
        values.append(value)
    return ", ".join(keys), values


async def create_admin_settings():
    account = await create_account()
    settings.super_user = account.id
    keys = []
    values = ""
    for key, value in settings.dict(exclude_none=True).items():
        if not key in readonly_variables:
            keys.append(key)
            if type(value) == list:
                joined = ",".join(value)
                values += f"'{joined}'"
            if type(value) == int or type(value) == float:
                values += str(value)
            if type(value) == bool:
                values += "true" if value else "false"
            if type(value) == str:
                value = value.replace("'", "")
                values += f"'{value}'"
            values += ","
    q = ", ".join(keys)
    v = values.rstrip(",")

    sql = f"INSERT INTO admin.settings ({q}) VALUES ({v})"
    await db.execute(sql)
