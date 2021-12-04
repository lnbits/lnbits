import asyncio
from email.message import EmailMessage

import aiosmtplib

from lnbits import settings as s


async def _send_mail_worker(mail: EmailMessage):
    mail["From"] = s.EMAIL_SENDER
    resp = await aiosmtplib.send(
        message=mail,
        hostname=s.SMTP_URL,
        port=s.SMTP_PORT,
        use_tls=True,
        username=s.SMTP_LOGIN,
        password=s.SMTP_PASSWORD,
    )
    return resp


async def send_mail_async(mail: EmailMessage):
    """Attempts to send an email and returns the result.

    Parameters
    ----------
    mail : [email.message.EmailMessage]
        [EmailMessage] from the email package
    """

    if not s.EMAIL_ENABLED:
        raise RuntimeError("LNBits Email system disabled")

    resp = await _send_mail_worker(mail)
    return resp


def send_mail_best_effort(mail: EmailMessage):
    """Fire and forget email sending.

    Will not return any errors
    Use this if you don't really care if the mail was sent or not.

    Parameters
    ----------
    mail: [email.message.EmailMessage]
        [email.message.EmailMessage] from the email package
    """

    if not s.EMAIL_ENABLED:
        raise RuntimeError("LNBits Email system disabled")

    loop = asyncio.get_event_loop()
    loop.create_task(_send_mail_worker(mail))
