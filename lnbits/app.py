import asyncio
import importlib
import logging
import os
import signal
import sys
import traceback
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from lnbits.core.tasks import register_task_listeners
from lnbits.settings import get_wallet_class, set_wallet_class, settings

from .commands import migrate_databases
from .core import core_app
from .core.services import check_admin_settings
from .core.views.generic import core_html_routes
from .helpers import (
    get_css_vendored,
    get_js_vendored,
    get_valid_extensions,
    template_renderer,
    url_for_vendored,
)
from .requestvars import g
from .tasks import (
    catch_everything_and_restart,
    check_pending_payments,
    internal_invoice_listener,
    invoice_listener,
    webhook_handler,
)


def create_app() -> FastAPI:

    configure_logger()

    app = FastAPI(
        title="LNbits API",
        description="API for LNbits, the free and open source bitcoin wallet and accounts system with plugins.",
        license_info={
            "name": "MIT License",
            "url": "https://raw.githubusercontent.com/lnbits/lnbits/main/LICENSE",
        },
    )

    app.mount("/static", StaticFiles(packages=[("lnbits", "static")]), name="static")
    app.mount(
        "/core/static",
        StaticFiles(packages=[("lnbits.core", "static")]),
        name="core_static",
    )

    g().base_url = f"http://{settings.host}:{settings.port}"

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    register_startup(app)
    register_assets(app)
    register_routes(app)
    register_async_tasks(app)
    register_exception_handlers(app)

    return app


async def check_funding_source() -> None:

    original_sigint_handler = signal.getsignal(signal.SIGINT)

    def signal_handler(signal, frame):
        logger.debug(f"SIGINT received, terminating LNbits.")
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    WALLET = get_wallet_class()
    while True:
        try:
            error_message, balance = await WALLET.status()
            if not error_message:
                break
            logger.error(
                f"The backend for {WALLET.__class__.__name__} isn't working properly: '{error_message}'",
                RuntimeWarning,
            )
        except:
            pass
        logger.info("Retrying connection to backend in 5 seconds...")
        await asyncio.sleep(5)
    signal.signal(signal.SIGINT, original_sigint_handler)
    logger.info(
        f"✔️ Backend {WALLET.__class__.__name__} connected and with a balance of {balance} msat."
    )


def register_routes(app: FastAPI) -> None:
    """Register FastAPI routes / LNbits extensions."""
    app.include_router(core_app)
    app.include_router(core_html_routes)

    for ext in get_valid_extensions():
        try:
            ext_module = importlib.import_module(f"lnbits.extensions.{ext.code}")
            ext_route = getattr(ext_module, f"{ext.code}_ext")

            if hasattr(ext_module, f"{ext.code}_start"):
                ext_start_func = getattr(ext_module, f"{ext.code}_start")
                ext_start_func()

            if hasattr(ext_module, f"{ext.code}_static_files"):
                ext_statics = getattr(ext_module, f"{ext.code}_static_files")
                for s in ext_statics:
                    app.mount(s["path"], s["app"], s["name"])

            logger.trace(f"adding route for extension {ext_module}")
            app.include_router(ext_route)
        except Exception as e:
            logger.error(str(e))
            raise ImportError(
                f"Please make sure that the extension `{ext.code}` follows conventions."
            )


def register_startup(app: FastAPI):
    @app.on_event("startup")
    async def lnbits_startup():

        try:
            # 1. wait till migration is done
            await migrate_databases()

            # 2. setup admin settings
            await check_admin_settings()

            log_server_info()

            # 3. initialize WALLET
            set_wallet_class()

            # 4. initialize funding source
            await check_funding_source()
        except Exception as e:
            logger.error(str(e))
            raise ImportError("Failed to run 'startup' event.")


def log_server_info():
    logger.info("Starting LNbits")
    logger.info(f"Host: {settings.host}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"Debug: {settings.debug}")
    logger.info(f"Site title: {settings.lnbits_site_title}")
    logger.info(f"Funding source: {settings.lnbits_backend_wallet_class}")
    logger.info(f"Data folder: {settings.lnbits_data_folder}")
    logger.info(f"Git version: {settings.lnbits_commit}")
    logger.info(f"Database: {get_db_vendor_name()}")
    logger.info(f"Service fee: {settings.lnbits_service_fee}")


def get_db_vendor_name():
    db_url = settings.lnbits_database_url
    return (
        "PostgreSQL"
        if db_url and db_url.startswith("postgres://")
        else "CockroachDB"
        if db_url and db_url.startswith("cockroachdb://")
        else "SQLite"
    )


def register_assets(app: FastAPI):
    """Serve each vendored asset separately or a bundle."""

    @app.on_event("startup")
    async def vendored_assets_variable():
        if settings.debug:
            g().VENDORED_JS = map(url_for_vendored, get_js_vendored())
            g().VENDORED_CSS = map(url_for_vendored, get_css_vendored())
        else:
            g().VENDORED_JS = ["/static/bundle.js"]
            g().VENDORED_CSS = ["/static/bundle.css"]


def register_async_tasks(app):
    @app.route("/wallet/webhook")
    async def webhook_listener():
        return await webhook_handler()

    @app.on_event("startup")
    async def listeners():
        loop = asyncio.get_event_loop()
        loop.create_task(catch_everything_and_restart(check_pending_payments))
        loop.create_task(catch_everything_and_restart(invoice_listener))
        loop.create_task(catch_everything_and_restart(internal_invoice_listener))
        await register_task_listeners()
        # await run_deferred_async() # calle: doesn't do anyting?

    @app.on_event("shutdown")
    async def stop_listeners():
        pass


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        etype, _, tb = sys.exc_info()
        traceback.print_exception(etype, exc, tb)
        logger.error(f"Exception: {str(exc)}")
        # Only the browser sends "text/html" request
        # not fail proof, but everything else get's a JSON response
        if (
            request.headers
            and "accept" in request.headers
            and "text/html" in request.headers["accept"]
        ):
            return template_renderer().TemplateResponse(
                "error.html", {"request": request, "err": f"Error: {str(exc)}"}
            )

        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        logger.error(f"RequestValidationError: {str(exc)}")
        # Only the browser sends "text/html" request
        # not fail proof, but everything else get's a JSON response

        if (
            request.headers
            and "accept" in request.headers
            and "text/html" in request.headers["accept"]
        ):
            return template_renderer().TemplateResponse(
                "error.html",
                {"request": request, "err": f"Error: {str(exc)}"},
            )

        return JSONResponse(
            status_code=HTTPStatus.BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.error(f"HTTPException {exc.status_code}: {exc.detail}")
        # Only the browser sends "text/html" request
        # not fail proof, but everything else get's a JSON response

        if (
            request.headers
            and "accept" in request.headers
            and "text/html" in request.headers["accept"]
        ):
            return template_renderer().TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "err": f"HTTP Error {exc.status_code}: {exc.detail}",
                },
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )


def configure_logger() -> None:
    logger.remove()
    log_level: str = "DEBUG" if settings.debug else "INFO"
    formatter = Formatter()
    logger.add(sys.stderr, level=log_level, format=formatter.format)

    if settings.file_log:
        # New log file is created each day at noon
        logger.add(
            os.path.join("lnbits.log"),
            level=log_level,
            format=formatter.format,
            rotation="12:00",
        )

    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]


class Formatter:
    def __init__(self):
        self.padding = 0
        self.minimal_fmt: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | <level>{level}</level> | <level>{message}</level>\n"
        if settings.debug:
            self.fmt: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | <level>{level: <4}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>\n"
        else:
            self.fmt: str = self.minimal_fmt

    def format(self, record):
        function = "{function}".format(**record)
        if function == "emit":  # uvicorn logs
            return self.minimal_fmt
        return self.fmt


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.log(level, record.getMessage())
