from typing import List, Optional, Union
from lnbits.helpers import urlsafe_short_hash

from http import HTTPStatus
from starlette.exceptions import HTTPException

from . import db
from .models import CreateEmailaddress, Emailaddresses, CreateEmail, Emails
from .smtp import send_mail

def get_test_mail(email, testemail):
    return CreateEmail(
            emailaddress_id=email,
            subject="LNBits Sendmail - Test Email",
            message="This is a test email from the lnbits LNsendmail extension! email is working!",
            receiver=testemail,
            )

async def create_emailaddress(data: CreateEmailaddress) -> Emailaddresses:

    emailaddress_id = urlsafe_short_hash()

    # send test mail for checking connection
    email = get_test_mail(data.email, data.testemail)
    await send_mail(data, email)

    await db.execute(
        """
        INSERT INTO sendmail.emailaddress (id, wallet, email, testemail, smtp_server, smtp_user, smtp_password, smtp_port, anonymize, description, cost)
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

async def update_emailaddress(emailaddress_id: str, **kwargs) -> Emailaddresses:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE sendmail.emailaddress SET {q} WHERE id = ?", (*kwargs.values(), emailaddress_id)
    )
    row = await db.fetchone(
        "SELECT * FROM sendmail.emailaddress WHERE id = ?", (emailaddress_id,)
    )

    # send test mail for checking connection
    email = get_test_mail(row.email, row.testemail)
    await send_mail(row, email)

    assert row, "Newly updated emailaddress couldn't be retrieved"
    return Emailaddresses(**row)


async def get_emailaddress(emailaddress_id: str) -> Optional[Emailaddresses]:
    row = await db.fetchone(
        "SELECT * FROM sendmail.emailaddress WHERE id = ?", (emailaddress_id,)
    )
    return Emailaddresses(**row) if row else None


async def get_emailaddress_by_email(email: str) -> Optional[Emailaddresses]:
    row = await db.fetchone(
        "SELECT * FROM sendmail.emailaddress WHERE email = ?", (email,)
    )
    return Emailaddresses(**row) if row else None

# async def get_emailAddressByEmail(email: str) -> Optional[Emails]:
#     row = await db.fetchone(
#         "SELECT s.*, d.emailaddress as emailaddress FROM sendmail.email s INNER JOIN sendmail.emailaddress d ON (s.emailaddress_id = d.id) WHERE s.emailaddress = ?",
#         (email,),
#     )
#     return Subdomains(**row) if row else None


async def get_emailaddresses(wallet_ids: Union[str, List[str]]) -> List[Emailaddresses]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM sendmail.emailaddress WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Emailaddresses(**row) for row in rows]


async def delete_emailaddress(emailaddress_id: str) -> None:
    await db.execute("DELETE FROM sendmail.emailaddress WHERE id = ?", (emailaddress_id,))


## create emails
async def create_email(payment_hash, wallet, data: CreateEmail) -> Emails:
    await db.execute(
        """
        INSERT INTO sendmail.email (id, wallet, emailaddress_id, subject, receiver, message, paid)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment_hash,
            wallet,
            data.emailaddress_id,
            data.subject,
            data.receiver,
            data.message,
            False,
        ),
    )

    new_email = await get_email(payment_hash)
    assert new_email, "Newly created email couldn't be retrieved"
    return new_email


async def set_email_paid(payment_hash: str) -> Emails:
    email = await get_email(payment_hash)
    if email.paid == False:
        await db.execute(
            """
            UPDATE sendmail.email
            SET paid = true
            WHERE id = ?
            """,
            (payment_hash,),
        )
    new_email = await get_email(payment_hash)
    assert new_email, "Newly paid email couldn't be retrieved"
    return new_email



async def get_email(email_id: str) -> Optional[Emails]:
    row = await db.fetchone(
        "SELECT s.*, d.email as emailaddress FROM sendmail.email s INNER JOIN sendmail.emailaddress d ON (s.emailaddress_id = d.id) WHERE s.id = ?",
        (email_id,),
    )
    return Emails(**row) if row else None




async def get_emails(wallet_ids: Union[str, List[str]]) -> List[Emails]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT s.*, d.email as emailaddress FROM sendmail.email s INNER JOIN sendmail.emailaddress d ON (s.emailaddress_id = d.id) WHERE s.wallet IN ({q})",
        (*wallet_ids,),
    )

    return [Emails(**row) for row in rows]


async def delete_email(email_id: str) -> None:
    await db.execute("DELETE FROM sendmail.email WHERE id = ?", (email_id,))

