from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateEmail, CreateEmailaddress, Email, Emailaddress
from .smtp import send_mail


def get_test_mail(email, testemail):
    return CreateEmail(
        emailaddress_id=email,
        subject="LNBits SMTP - Test Email",
        message="This is a test email from the LNBits SMTP extension! email is working!",
        receiver=testemail,
    )


async def create_emailaddress(data: CreateEmailaddress) -> Emailaddress:

    emailaddress_id = urlsafe_short_hash()

    # send test mail for checking connection
    email = get_test_mail(data.email, data.testemail)
    await send_mail(data, email)

    await db.execute(
        """
        INSERT INTO smtp.emailaddress (id, wallet, email, testemail, smtp_server, smtp_user, smtp_password, smtp_port, anonymize, description, cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            emailaddress_id,
            data.wallet,
            data.email,
            data.testemail,
            data.smtp_server,
            data.smtp_user,
            data.smtp_password,
            data.smtp_port,
            data.anonymize,
            data.description,
            data.cost,
        ),
    )

    new_emailaddress = await get_emailaddress(emailaddress_id)
    assert new_emailaddress, "Newly created emailaddress couldn't be retrieved"
    return new_emailaddress


async def update_emailaddress(emailaddress_id: str, **kwargs) -> Emailaddress:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE smtp.emailaddress SET {q} WHERE id = ?",
        (*kwargs.values(), emailaddress_id),
    )
    row = await db.fetchone(
        "SELECT * FROM smtp.emailaddress WHERE id = ?", (emailaddress_id,)
    )

    # send test mail for checking connection
    email = get_test_mail(row.email, row.testemail)
    await send_mail(row, email)

    assert row, "Newly updated emailaddress couldn't be retrieved"
    return Emailaddress(**row)


async def get_emailaddress(emailaddress_id: str) -> Optional[Emailaddress]:
    row = await db.fetchone(
        "SELECT * FROM smtp.emailaddress WHERE id = ?", (emailaddress_id,)
    )
    return Emailaddress(**row) if row else None


async def get_emailaddress_by_email(email: str) -> Optional[Emailaddress]:
    row = await db.fetchone("SELECT * FROM smtp.emailaddress WHERE email = ?", (email,))
    return Emailaddress(**row) if row else None


async def get_emailaddresses(wallet_ids: Union[str, List[str]]) -> List[Emailaddress]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM smtp.emailaddress WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Emailaddress(**row) for row in rows]


async def delete_emailaddress(emailaddress_id: str) -> None:
    await db.execute("DELETE FROM smtp.emailaddress WHERE id = ?", (emailaddress_id,))


async def create_email(wallet: str, data: CreateEmail, payment_hash: str = "") -> Email:
    id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO smtp.email (id, payment_hash, wallet, emailaddress_id, subject, receiver, message, paid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            id,
            payment_hash,
            wallet,
            data.emailaddress_id,
            data.subject,
            data.receiver,
            data.message,
            False,
        ),
    )

    new_email = await get_email(id)
    assert new_email, "Newly created email couldn't be retrieved"
    return new_email


async def set_email_paid(payment_hash: str) -> bool:
    email = await get_email_by_payment_hash(payment_hash)
    if email and email.paid == False:
        await db.execute(
            f"UPDATE smtp.email SET paid = true WHERE payment_hash = ?", (payment_hash,)
        )
        return True
    return False


async def get_email_by_payment_hash(payment_hash: str) -> Optional[Email]:
    row = await db.fetchone(
        f"SELECT * FROM smtp.email WHERE payment_hash = ?", (payment_hash,)
    )
    return Email(**row) if row else None


async def get_email(id: str) -> Optional[Email]:
    row = await db.fetchone(f"SELECT * FROM smtp.email WHERE id = ?", (id,))
    return Email(**row) if row else None


async def get_emails(wallet_ids: Union[str, List[str]]) -> List[Email]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT s.*, d.email as emailaddress FROM smtp.email s INNER JOIN smtp.emailaddress d ON (s.emailaddress_id = d.id) WHERE s.wallet IN ({q})",
        (*wallet_ids,),
    )

    return [Email(**row) for row in rows]


async def delete_email(email_id: str) -> None:
    await db.execute("DELETE FROM smtp.email WHERE id = ?", (email_id,))
