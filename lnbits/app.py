import jinja2
from lnbits.jinja2_templating import Jinja2Templates
import sys
import warnings
import importlib
import traceback
import trio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .commands import db_migrate, handle_assets
from .core import core_app
from .helpers import (
    get_valid_extensions,
    get_js_vendored,
    get_css_vendored,
    url_for_vendored,
)
from .proxy_fix import ASGIProxyFix
from .tasks import (
    webhook_handler,
    invoice_listener,
    run_deferred_async,
    check_pending_payments,
    internal_invoice_listener,
    catch_everything_and_restart,
)
from .settings import WALLET
from .requestvars import g, request_global
from .core.views.generic import core_html_routes
import lnbits.settings

async def create_app(config_object="lnbits.settings") -> FastAPI:
    """Create application factory.
    :param config_object: The configuration object to use.
    """
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="lnbits/static"), name="static")
    app.mount("/core/static", StaticFiles(directory="lnbits/core/static"), name="core_static")

    origins = [
        "http://localhost",
        "http://localhost:5000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    g().config = lnbits.settings
    g().templates = build_standard_jinja_templates()

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    # app.add_middleware(ASGIProxyFix)

    check_funding_source(app)
    register_assets(app)
    register_routes(app)
    # register_commands(app)
    register_async_tasks(app)
    # register_exception_handlers(app)

    return app

def build_standard_jinja_templates():
    t = Jinja2Templates(
     loader=jinja2.FileSystemLoader(["lnbits/templates", "lnbits/core/templates"]),
    )
    t.env.globals["SITE_TITLE"] = lnbits.settings.LNBITS_SITE_TITLE
    t.env.globals["SITE_TAGLINE"] = lnbits.settings.LNBITS_SITE_TAGLINE
    t.env.globals["SITE_DESCRIPTION"] = lnbits.settings.LNBITS_SITE_DESCRIPTION
    t.env.globals["LNBITS_THEME_OPTIONS"] = lnbits.settings.LNBITS_THEME_OPTIONS
    t.env.globals["LNBITS_VERSION"] = lnbits.settings.LNBITS_COMMIT
    t.env.globals["EXTENSIONS"] = get_valid_extensions()
    
    if g().config.DEBUG:
        t.env.globals["VENDORED_JS"] = map(url_for_vendored, get_js_vendored())
        t.env.globals["VENDORED_CSS"] = map(url_for_vendored, get_css_vendored())
    else:
        t.env.globals["VENDORED_JS"] = ["/static/bundle.js"]
        t.env.globals["VENDORED_CSS"] = ["/static/bundle.css"]

    return t

def check_funding_source(app: FastAPI) -> None:
    @app.on_event("startup")
    async def check_wallet_status():
        error_message, balance = await WALLET.status()
        if error_message:
            warnings.warn(
                f"  × The backend for {WALLET.__class__.__name__} isn't working properly: '{error_message}'",
                RuntimeWarning,
            )

            sys.exit(4)
        else:
            print(
                f"  ✔️ {WALLET.__class__.__name__} seems to be connected and with a balance of {balance} msat."
            )


def register_routes(app: FastAPI) -> None:
    """Register FastAPI routes / LNbits extensions."""
    app.include_router(core_app)
    app.include_router(core_html_routes)

    for ext in get_valid_extensions():
        try:
            ext_module = importlib.import_module(f"lnbits.extensions.{ext.code}")
            ext_route = getattr(ext_module, f"{ext.code}_ext")

            app.include_router(ext_route)
        except Exception:
            raise ImportError(
                f"Please make sure that the extension `{ext.code}` follows conventions."
            )


def register_commands(app: FastAPI):
    """Register Click commands."""
    app.cli.add_command(db_migrate)
    app.cli.add_command(handle_assets)


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
        run_deferred_async()
        trio.open_process(check_pending_payments)
        trio.open_process(invoice_listener)
        trio.open_process(internal_invoice_listener)
        
        async with trio.open_nursery() as n:
            pass
            # n.start_soon(catch_everything_and_restart, check_pending_payments)
            # n.start_soon(catch_everything_and_restart, invoice_listener)
            # n.start_soon(catch_everything_and_restart, internal_invoice_listener)

    @app.on_event("shutdown")
    async def stop_listeners():
        pass


def register_exception_handlers(app):
    @app.errorhandler(Exception)
    async def basic_error(err):
        print("handled error", traceback.format_exc())
        etype, value, tb = sys.exc_info()
        traceback.print_exception(etype, err, tb)
        exc = traceback.format_exc()
        return (
            "\n\n".join(
                [
                    "LNbits internal error!",
                    exc,
                    "If you believe this shouldn't be an error please bring it up on https://t.me/lnbits",
                ]
            ),
            500,
        )
