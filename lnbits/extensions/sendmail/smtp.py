import sys
import os
import re
import socket

from http import HTTPStatus
from starlette.exceptions import HTTPException

from smtplib import SMTP_SSL as SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def valid_email(s):
    # https://regexr.com/2rhq7
    pat = "[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    if re.match(pat,s):
        return True
    raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f'invalid email: {s}.')

async def send_mail(emailaddress, email):
    valid_email(emailaddress.email)
    valid_email(email.receiver)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = email.subject
    msg['From'] = emailaddress.email
    msg['To'] = email.receiver

    signature = "Email sent anonymiously by LNbits Sendmail extension."
    text = """\
        """ + email.message +  """

        """ + signature +  """
    """

    html = """\
    <html>
      <head></head>
      <body>
        <p>""" + email.message + """<p>
        <p><br>""" + signature + """</p>
      </body>
    </html>
    """
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)

    try:
        conn = SMTP(host=emailaddress.smtp_server, port=emailaddress.smtp_port, timeout=10)
        # conn.set_debuglevel(True)
    except socket.error as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f'error connecting to smtp server: {str(e)}.')
    try:
        conn.login(emailaddress.smtp_user, emailaddress.smtp_password)
    except socket.error as e:
        raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f'error login into smtp {emailaddress.smtp_user}:{emailaddress.smtp_password}. {str(e)}'
                )
    try:
        conn.sendmail(emailaddress.email, email.receiver, msg.as_string())
    except socket.error as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f'error sending email: {str(e)}.')
    finally:
        conn.quit()
