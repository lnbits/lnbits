import asyncio

import uvloop
from starlette.requests import Request

from .commands import bundle_vendored, migrate_databases, transpile_scss
from .settings import (
    DEBUG,
    LNBITS_COMMIT,
    LNBITS_DATA_FOLDER,
    LNBITS_SITE_TITLE,
    PORT,
    SERVICE_FEE,
    WALLET,
)

uvloop.install()

asyncio.create_task(migrate_databases())
transpile_scss()
bundle_vendored()

from .app import create_app

app = create_app()

print(
    f"""Starting LNbits with
  - git version: {LNBITS_COMMIT}
  - site title: {LNBITS_SITE_TITLE}
  - debug: {DEBUG}
  - data folder: {LNBITS_DATA_FOLDER}
  - funding source: {WALLET.__class__.__name__}
  - service fee: {SERVICE_FEE}
"""
)
