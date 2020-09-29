import asyncio
from typing import Optional, Awaitable
from quart import Quart, Request, g
from werkzeug.datastructures import Headers

from lnbits.db import open_db

main_app: Optional[Quart] = None


def grab_app_for_later(state):
    global main_app
    main_app = state.app


def run_on_pseudo_request(awaitable: Awaitable):
    async def run(awaitable):
        fk = Request(
            "GET",
            "http",
            "/background/pseudo",
            b"",
            Headers([("host", "lnbits.background")]),
            "",
            "1.1",
            send_push_promise=lambda x, h: None,
        )
        async with main_app.request_context(fk):
            g.db = open_db()
            await awaitable

    loop = asyncio.get_event_loop()
    loop.create_task(run(awaitable))
