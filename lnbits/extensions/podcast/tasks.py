import asyncio
import json

import httpx

from lnbits.core import db as core_db
from lnbits.core.models import Podcastment
from lnbits.tasks import register_invoice_listener

from .crud import get_Podcast_pod


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue)

    while True:
        Podcastment = await invoice_queue.get()
        await on_invoice_paid(Podcastment)


async def on_invoice_paid(Podcastment: Podcastment) -> None:
    if Podcastment.extra.get("tag") != "podcast":
        # not an podcast invoice
        return

    if Podcastment.extra.get("wh_status"):
        # this webhook has already been sent
        return

    Podcast = await get_Podcast_pod(Podcastment.extra.get("pod", -1))
    if Podcast and Podcast.webhook_url:
        async with httpx.AsyncClient() as client:
            try:
                r = await client.post(
                    Podcast.webhook_url,
                    json={
                        "Podcastment_hash": Podcastment.Podcastment_hash,
                        "Podcastment_request": Podcastment.bolt11,
                        "amount": Podcastment.amount,
                        "comment": Podcastment.extra.get("comment"),
                        "podcast": Podcast.id,
                    },
                    timeout=40,
                )
                await mark_webhook_sent(Podcastment, r.status_code)
            except (httpx.ConnectError, httpx.RequestError):
                await mark_webhook_sent(Podcastment, -1)


async def mark_webhook_sent(Podcastment: Podcastment, status: int) -> None:
    Podcastment.extra["wh_status"] = status

    await core_db.execute(
        """
        UPDATE apiPodcastments SET extra = ?
        WHERE hash = ?
        """,
        (json.dumps(Podcastment.extra), Podcastment.Podcastment_hash),
    )
