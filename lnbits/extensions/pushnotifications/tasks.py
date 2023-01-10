import asyncio
import json
import os

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid, b64urlencode
from pywebpush import WebPushException, webpush

from lnbits.core.crud import get_wallet
from lnbits.core.models import Payment
from lnbits.settings import settings
from lnbits.tasks import register_invoice_listener

from .crud import create_subscription, delete_subscriptions, get_subscriptions_by_wallet

vapid_key_file = os.path.join(
    settings.lnbits_data_folder, "ext_pushnotifications_vapid.{}"
)


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


def create_vapid_key_pair():
    """
    Generates VAPID private and public key file if they don't exist yet
    """
    private_key = Vapid().from_file(vapid_key_file.format("private"))

    if not os.path.exists(vapid_key_file.format("public")):
        public_key = private_key.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        f = open(vapid_key_file.format("public"), "w")
        f.write(b64urlencode(public_key))


def get_vapid_public_key():
    private_key = Vapid().from_file(vapid_key_file.format("private"))
    public_key = private_key.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64urlencode(public_key)


async def on_invoice_paid(payment: Payment) -> None:
    wallet = await get_wallet(payment.wallet_id)
    subscriptions = await get_subscriptions_by_wallet(wallet.id)

    amount = int(payment.amount / 1000)
    comment = payment.extra.get("comment")

    title = f"LNbits: {wallet.name}"
    body = f"You just received {amount} sat{'s'[:amount^1]}!"

    if payment.memo:
        body += f"\r\n{payment.memo}"

    if comment:
        body += f"\r\n{comment}"

    for subscription in subscriptions:
        url = f"https://{subscription.host}/wallet?usr={wallet.user}&wal={wallet.id}"
        send_push_notification(subscription, title, body, url)


def send_push_notification(subscription, title, body, url=""):
    try:
        webpush(
            json.loads(subscription.data),
            json.dumps({"title": title, "body": body, "url": url}),
            Vapid().from_file(vapid_key_file.format("private")),
            {"aud": "", "sub": "mailto:alan@lnbits.com"},
        )
    except WebPushException as e:
        """
        This should clean up the database over time from stale endpoints
        """
        delete_subscriptions(subscription.endpoint)
        return
