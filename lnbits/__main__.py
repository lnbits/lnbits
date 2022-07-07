import asyncio

import uvloop
from starlette.requests import Request

from loguru import logger

from .commands import bundle_vendored, migrate_databases, transpile_scss
from .settings import (
    DEBUG,
    LNBITS_COMMIT,
    LNBITS_DATA_FOLDER,
    LNBITS_SITE_TITLE,
    HOST,
    PORT,
    WALLET,
    LNBITS_DATABASE_URL,
    LNBITS_DATA_FOLDER,
)

uvloop.install()

asyncio.create_task(migrate_databases())
transpile_scss()
bundle_vendored()

from .app import create_app

app = create_app()

logger.info("Starting LNbits")
logger.info(f"Host: {HOST}")
logger.info(f"Port: {PORT}")
logger.info(f"Debug: {DEBUG}")
logger.info(f"Site title: {LNBITS_SITE_TITLE}")
logger.info(f"Funding source: {WALLET.__class__.__name__}")
logger.info(
    f"Database: {'PostgreSQL' if LNBITS_DATABASE_URL and LNBITS_DATABASE_URL.startswith('postgres://') else 'CockroachDB' if LNBITS_DATABASE_URL and LNBITS_DATABASE_URL.startswith('cockroachdb://') else 'SQLite'}"
)
logger.info(f"Data folder: {LNBITS_DATA_FOLDER}")
logger.info(f"Git version: {LNBITS_COMMIT}")
# logger.info(f"Service fee: {SERVICE_FEE}")
