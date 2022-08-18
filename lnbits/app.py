import asyncio
import importlib
import logging
import signal
import sys
import traceback
import warnings
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

import lnbits.settings
from lnbits.core.tasks import register_task_listeners

from .core import core_app
from .core.views.generic import core_html_routes
from .helpers import (
    get_css_vendored,
    get_js_vendored,
    get_valid_extensions,
    template_renderer,
    url_for_vendored,
)
from .requestvars import g
from .settings import WALLET
from .tasks import (
    catch_everything_and_restart,
    check_pending_payments,
    internal_invoice_listener,
    invoice_listener,
    run_deferred_async,
    webhook_handler,
)


def create_app(config_object="lnbits.settings") -> FastAPI:
    """Create application factory.
    :param config_object: The configuration object to use.
    """
    configure_logger()

    app = FastAPI(
        title="LNbits API",
        description="API for LNbits, the free and open source bitcoin wallet and accounts system with plugins.",
        license_info={
            "name": "MIT License",
            "url": "https://raw.githubusercontent.com/lnbits/lnbits-legend/main/LICENSE",
        },
    )
    app.mount("/static", StaticFiles(packages=[("lnbits", "static")]), name="static")
    app.mount(
        "/core/static",
        StaticFiles(packages=[("lnbits.core", "static")]),
        name="core_static",
    )

    origins = ["*"]

    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"]
    )

    g().config = lnbits.settings
    g().base_url = f"http://{lnbits.settings.HOST}:{lnbits.settings.PORT}"

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        # Only the browser sends "text/html" request
        # not fail proof, but everything else get's a JSON response

        if (
            request.headers
            and "accept" in request.headers
            and "text/html" in request.headers["accept"]
        ):
            return template_renderer().TemplateResponse(
                "error.html",
                {"request": request, "err": f"{exc.errors()} is not a valid UUID."},
            )

        return JSONResponse(
            status_code=HTTPStatus.NO_CONTENT,
            content={"detail": exc.errors()},
        )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    # app.add_middleware(ASGIProxyFix)

    check_funding_source(app)
    register_assets(app)
    register_routes(app)
    register_async_tasks(app)
    register_exception_handlers(app)

    return app


def check_funding_source(app: FastAPI) -> None:
    @app.on_event("startup")
    async def check_wallet_status():
        original_sigint_handler = signal.getsignal(signal.SIGINT)

        def signal_handler(signal, frame):
            logger.debug(f"SIGINT received, terminating LNbits.")
            sys.exit(1)

        signal.signal(signal.SIGINT, signal_handler)
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


def register_assets(app: FastAPI):
    """Serve each vendored asset separately or a bundle."""

    @app.on_event("startup")
    async def vendored_assets_variable():
        if g().config.DEBUG:
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
        await run_deferred_async()

    @app.on_event("shutdown")
    async def stop_listeners():
        pass


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(Exception)
    async def basic_error(request: Request, err):
        logger.error("handled error", traceback.format_exc())
        logger.error("ERROR:", err)
        etype, _, tb = sys.exc_info()
        traceback.print_exception(etype, err, tb)
        exc = traceback.format_exc()

        if (
            request.headers
            and "accept" in request.headers
            and "text/html" in request.headers["accept"]
        ):
            return template_renderer().TemplateResponse(
                "error.html", {"request": request, "err": err}
            )

        return JSONResponse(
            status_code=HTTPStatus.NO_CONTENT,
            content={"detail": err},
        )


def configure_logger() -> None:
    logger.remove()
    log_level: str = "DEBUG" if lnbits.settings.DEBUG else "INFO"
    formatter = Formatter()
    logger.add(sys.stderr, level=log_level, format=formatter.format)

    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]


class Formatter:
    def __init__(self):
        self.padding = 0
        self.minimal_fmt: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | <level>{level}</level> | <level>{message}</level>\n"
        if lnbits.settings.DEBUG:
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
