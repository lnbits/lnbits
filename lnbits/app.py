import asyncio
import importlib
import sys
import traceback
import warnings

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

import lnbits.settings
from lnbits.core.tasks import register_task_listeners

from .commands import db_migrate, get_admin_settings, handle_assets
from .config import WALLET, conf
from .core import core_app
from .core.views.generic import core_html_routes
from .helpers import (
    get_css_vendored,
    get_js_vendored,
    get_valid_extensions,
    removeEmptyString,
    template_renderer,
    url_for_vendored,
)
from .requestvars import g

# from .settings import WALLET
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
    app = FastAPI()
    if lnbits.settings.LNBITS_ADMIN_UI:
        g().admin_conf = conf
        check_settings(app)

    g().WALLET = WALLET
    app.mount("/static", StaticFiles(directory="lnbits/static"), name="static")
    app.mount(
        "/core/static", StaticFiles(directory="lnbits/core/static"), name="core_static"
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
        return template_renderer().TemplateResponse(
            "error.html",
            {"request": request, "err": f"`{exc.errors()}` is not a valid UUID."},
        )

        # return HTMLResponse(
        #     status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        #     content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
        # )

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    # app.add_middleware(ASGIProxyFix)

    check_funding_source(app)
    register_assets(app)
    register_routes(app)
    # register_commands(app)
    register_async_tasks(app)
    register_exception_handlers(app)

    return app

def check_settings(app: FastAPI):
    @app.on_event("startup")
    async def check_settings_admin():

        while True:
            admin_set = await get_admin_settings()
            if admin_set :
                break
            print("ERROR:", admin_set)
            await asyncio.sleep(5)
            
        admin_set.admin_users = removeEmptyString(admin_set.admin_users.split(','))
        admin_set.allowed_users = removeEmptyString(admin_set.allowed_users.split(','))
        admin_set.admin_ext = removeEmptyString(admin_set.admin_ext.split(','))
        admin_set.disabled_ext = removeEmptyString(admin_set.disabled_ext.split(','))
        admin_set.theme = removeEmptyString(admin_set.theme.split(','))
        admin_set.ad_space = removeEmptyString(admin_set.ad_space.split(','))
        g().admin_conf = conf.copy(update=admin_set.dict())

def check_funding_source(app: FastAPI) -> None:
    @app.on_event("startup")
    async def check_wallet_status():
        while True:
            error_message, balance = await WALLET.status()
            if not error_message:
                break
            warnings.warn(
                f"  × The backend for {WALLET.__class__.__name__} isn't working properly: '{error_message}'",
                RuntimeWarning,
            )
            print("Retrying connection to backend in 5 seconds...")
            await asyncio.sleep(5)
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

            if hasattr(ext_module, f"{ext.code}_start"):
                ext_start_func = getattr(ext_module, f"{ext.code}_start")
                ext_start_func()

            if hasattr(ext_module, f"{ext.code}_static_files"):
                ext_statics = getattr(ext_module, f"{ext.code}_static_files")
                for s in ext_statics:
                    app.mount(s["path"], s["app"], s["name"])

            app.include_router(ext_route)
        except Exception as e:
            print(str(e))
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
        print("handled error", traceback.format_exc())
        etype, _, tb = sys.exc_info()
        traceback.print_exception(etype, err, tb)
        exc = traceback.format_exc()
        return template_renderer().TemplateResponse(
            "error.html", {"request": request, "err": err}
        )
