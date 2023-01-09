import re
import socket
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from http import HTTPStatus
from smtplib import SMTP_SSL as SMTP

from loguru import logger
from starlette.exceptions import HTTPException


def valid_email(s):
    # https://regexr.com/2rhq7
    pat = "[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    if re.match(pat, s):
        return True
    msg = f"SMTP - invalid email: {s}."
    logger.error(msg)
    raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=msg)


async def send_mail(emailaddress, email):
    valid_email(emailaddress.email)
    valid_email(email.receiver)

    ts = time.time()
    date = formatdate(ts, True)

    msg = MIMEMultipart("alternative")
    msg = MIMEMultipart("alternative")
    msg["Date"] = date
    msg["Subject"] = email.subject
    msg["From"] = emailaddress.email
    msg["To"] = email.receiver

    signature = "Email sent anonymiously by LNbits Sendmail extension."
    text = (
        """\
        """
        + email.message
        + """
        """
        + signature
        + """
    """
    )

    html = (
        """\
    <html>
      <head></head>
      <body>
        <p>"""
        + email.message
        + """<p>
        <p><br>"""
        + signature
        + """</p>
      </body>
    </html>
    """
    )
    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")
    msg.attach(part1)
    msg.attach(part2)

    try:
        conn = SMTP(
            host=emailaddress.smtp_server, port=emailaddress.smtp_port, timeout=10
        )
        logger.debug("SMTP - connected to smtp server.")
        # conn.set_debuglevel(True)
    except:
        msg = f"SMTP - error connecting to smtp server: {emailaddress.smtp_server}:{emailaddress.smtp_port}."
        logger.error(msg)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=msg)
    try:
        conn.login(emailaddress.smtp_user, emailaddress.smtp_password)
        logger.debug("SMTP - successful login to smtp server.")
    except:
        msg = f"SMTP - error login into smtp {emailaddress.smtp_user}."
        logger.error(msg)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=msg)
    try:
        conn.sendmail(emailaddress.email, email.receiver, msg.as_string())
        logger.debug("SMTP - successfully send email.")
    except socket.error as e:
        msg = f"SMTP - error sending email: {str(e)}."
        logger.error(msg)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=msg)
    finally:
        conn.quit()
