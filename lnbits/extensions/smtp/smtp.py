import re
import socket
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from smtplib import SMTP_SSL as SMTP
from typing import Union

from loguru import logger

from .models import CreateEmail, CreateEmailaddress, Email, Emailaddress


async def send_mail(
    emailaddress: Union[Emailaddress, CreateEmailaddress],
    email: Union[Email, CreateEmail],
):
    smtp_client = SmtpService(emailaddress)
    message = smtp_client.create_message(email)
    await smtp_client.send_mail(email.receiver, message)


def valid_email(s):
    # https://regexr.com/2rhq7
    pat = r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    if re.match(pat, s):
        return True
    log = f"SMTP - invalid email: {s}."
    logger.error(log)
    raise Exception(log)


class SmtpService:
    def __init__(self, emailaddress: Union[Emailaddress, CreateEmailaddress]) -> None:
        self.sender = emailaddress.email
        self.smtp_server = emailaddress.smtp_server
        self.smtp_port = emailaddress.smtp_port
        self.smtp_user = emailaddress.smtp_user
        self.smtp_password = emailaddress.smtp_password

    def render_email(self, email: Union[Email, CreateEmail]):
        signature: str = "Email sent by LNbits SMTP extension."
        text = f"{email.message}\n\n{signature}"
        html = (
            """
        <html>
          <head></head>
          <body>
            <p>"""
            + email.message
            + """</p>
            <p>"""
            + signature
            + """</p>
          </body>
        </html>
        """
        )
        return text, html

    def create_message(self, email: Union[Email, CreateEmail]):
        ts = time.time()
        date = formatdate(ts, True)

        msg = MIMEMultipart("alternative")
        msg["Date"] = date
        msg["Subject"] = email.subject
        msg["From"] = self.sender
        msg["To"] = email.receiver

        text, html = self.render_email(email)

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        msg.attach(part1)
        msg.attach(part2)
        return msg

    async def send_mail(self, receiver, msg: MIMEMultipart):

        valid_email(self.sender)
        valid_email(receiver)

        try:
            conn = SMTP(host=self.smtp_server, port=int(self.smtp_port), timeout=10)
            logger.debug("SMTP - connected to smtp server.")
            # conn.set_debuglevel(True)
        except:
            log = f"SMTP - error connecting to smtp server: {self.smtp_server}:{self.smtp_port}."
            logger.debug(log)
            raise Exception(log)

        try:
            conn.login(self.smtp_user, self.smtp_password)
            logger.debug("SMTP - successful login to smtp server.")
        except:
            log = f"SMTP - error login into smtp {self.smtp_user}."
            logger.error(log)
            raise Exception(log)

        try:
            conn.sendmail(self.sender, receiver, msg.as_string())
            logger.debug("SMTP - successfully send email.")
        except socket.error as e:
            log = f"SMTP - error sending email: {str(e)}."
            logger.error(log)
            raise Exception(log)
        finally:
            conn.quit()
