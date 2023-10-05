import asyncio
import glob
import importlib
import logging
import os
import shutil
import signal
import sys
import traceback
from hashlib import sha256
from http import HTTPStatus
from pathlib import Path
from typing import Callable, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from lnbits.core.crud import get_installed_extensions
from lnbits.core.helpers import migrate_extension_database
from lnbits.core.services import websocketUpdater
from lnbits.core.tasks import (  # register_watchdog,; unregister_watchdog,
    register_killswitch,
    register_task_listeners,
)
from lnbits.settings import settings
from lnbits.tasks import cancel_all_tasks, create_permanent_task
from lnbits.utils.cache import cache
from lnbits.wallets import get_wallet_class, set_wallet_class

from .commands import db_versions, load_disabled_extension_list, migrate_databases
from .core import init_core_routers
from .core.db import core_app_extra
from .core.services import check_admin_settings, check_webpush_settings
from .core.views.api import add_installed_extension
from .core.views.generic import update_installed_extension_state
from .extension_manager import Extension, InstallableExtension, get_valid_extensions
from .helpers import template_renderer
from .middleware import (
    CustomGZipMiddleware,
    ExtensionsRedirectMiddleware,
    InstalledExtensionMiddleware,
    add_ip_block_middleware,
    add_ratelimit_middleware,
)
from .requestvars import g
from .tasks import (
    check_pending_payments,
    internal_invoice_listener,
    invoice_listener,
    webhook_handler,
)


def create_app() -> FastAPI:
    configure_logger()
    app = FastAPI(
        title=settings.lnbits_title,
        description=(
            "API for LNbits, the free and open source bitcoin wallet and "
            "accounts system with plugins."
        ),
        version=settings.version,
        license_info={
            "name": "MIT License",
            "url": "https://raw.githubusercontent.com/lnbits/lnbits/main/LICENSE",
        },
    )

    # Allow registering new extensions routes without direct access to the `app` object
    setattr(core_app_extra, "register_new_ext_routes", register_new_ext_routes(app))
    setattr(core_app_extra, "register_new_ratelimiter", register_new_ratelimiter(app))

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

    app.add_middleware(
        CustomGZipMiddleware, minimum_size=1000, exclude_paths=["/api/v1/payments/sse"]
    )

    # order of these two middlewares is important
    app.add_middleware(InstalledExtensionMiddleware)
    app.add_middleware(ExtensionsRedirectMiddleware)

    register_custom_extensions_path()

    # adds security middleware
    add_ip_block_middleware(app)
    add_ratelimit_middleware(app)

    register_startup(app)
    register_routes(app)
    register_async_tasks(app)
    register_exception_handlers(app)
    register_shutdown(app)

    return app


async def check_funding_source() -> None:
    original_sigint_handler = signal.getsignal(signal.SIGINT)

    def signal_handler(signal, frame):
        logger.debug(
            f"SIGINT received, terminating LNbits. signal: {signal}, frame: {frame}"
        )
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    WALLET = get_wallet_class()

    # fallback to void after 30 seconds of failures
    sleep_time = 5
    timeout = int(30 / sleep_time)

    balance = 0
    retry_counter = 0

    while True:
        try:
            error_message, balance = await WALLET.status()
            if not error_message:
                retry_counter = 0
                break

            logger.error(
                f"The backend for {WALLET.__class__.__name__} isn't "
                f"working properly: '{error_message}'",
                RuntimeWarning,
            )
        except Exception as e:
            logger.error(f"Error connecting to {WALLET.__class__.__name__}: {e}")
            pass

        if settings.lnbits_admin_ui and retry_counter == timeout:
            set_void_wallet_class()
            WALLET = get_wallet_class()
            break
        else:
            logger.warning(f"Retrying connection to backend in {sleep_time} seconds...")
            retry_counter += 1
            await asyncio.sleep(sleep_time)

    signal.signal(signal.SIGINT, original_sigint_handler)

    logger.info(
        f"✔️ Backend {WALLET.__class__.__name__} connected "
        f"and with a balance of {balance} msat."
    )


def set_void_wallet_class():
    logger.warning(
        "Fallback to VoidWallet, because the backend for "
        f"{settings.lnbits_backend_wallet_class} isn't working properly"
    )
    set_wallet_class("VoidWallet")


async def check_installed_extensions(app: FastAPI):
    """
    Check extensions that have been installed, but for some reason no longer present in
    the 'lnbits/extensions' directory. One reason might be a docker-container that was
    re-created. The 'data' directory (where the '.zip' files live) is expected to
    persist state. Zips that are missing will be re-downloaded.
    """
    shutil.rmtree(os.path.join("lnbits", "upgrades"), True)
    await load_disabled_extension_list()
    installed_extensions = await build_all_installed_extensions_list()

    for ext in installed_extensions:
        try:
            installed = check_installed_extension_files(ext)
            if not installed:
                await restore_installed_extension(app, ext)
                logger.info(
                    "✔️ Successfully re-installed extension: "
                    f"{ext.id} ({ext.installed_version})"
                )
        except Exception as e:
            logger.warning(e)
            logger.warning(
                f"Failed to re-install extension: {ext.id} ({ext.installed_version})"
            )

    logger.info(f"Installed Extensions ({len(installed_extensions)}):")
    for ext in installed_extensions:
        logger.info(f"{ext.id} ({ext.installed_version})")


async def build_all_installed_extensions_list() -> List[InstallableExtension]:
    """
    Returns a list of all the installed extensions plus the extensions that
    MUST be installed by default (see LNBITS_EXTENSIONS_DEFAULT_INSTALL).
    """
    installed_extensions = await get_installed_extensions()

    installed_extensions_ids = [e.id for e in installed_extensions]
    for ext_id in settings.lnbits_extensions_default_install:
        if ext_id in installed_extensions_ids:
            continue

        ext_releases = await InstallableExtension.get_extension_releases(ext_id)
        release = ext_releases[0] if len(ext_releases) else None

        if release:
            ext_info = InstallableExtension(
                id=ext_id, name=ext_id, installed_release=release, icon=release.icon
            )
            installed_extensions.append(ext_info)

    return installed_extensions


def check_installed_extension_files(ext: InstallableExtension) -> bool:
    if ext.has_installed_version:
        return True

    zip_files = glob.glob(os.path.join(settings.lnbits_data_folder, "zips", "*.zip"))

    if f"./{str(ext.zip_path)}" not in zip_files:
        ext.download_archive()
    ext.extract_archive()

    return False


async def restore_installed_extension(app: FastAPI, ext: InstallableExtension):
    await add_installed_extension(ext)
    await update_installed_extension_state(ext_id=ext.id, active=True)

    extension = Extension.from_installable_ext(ext)
    register_ext_routes(app, extension)

    current_version = (await db_versions()).get(ext.id, 0)
    await migrate_extension_database(extension, current_version)

    # mount routes for the new version
    core_app_extra.register_new_ext_routes(extension)
    if extension.upgrade_hash:
        ext.nofiy_upgrade()


def register_routes(app: FastAPI) -> None:
    """Register FastAPI routes / LNbits extensions."""
    init_core_routers(app)

    for ext in get_valid_extensions():
        try:
            register_ext_routes(app, ext)
        except Exception as e:
            logger.error(f"Could not load extension `{ext.code}`: {str(e)}")


def register_custom_extensions_path():
    if settings.has_default_extension_path:
        return
    default_ext_path = os.path.join("lnbits", "extensions")
    if os.path.isdir(default_ext_path) and len(os.listdir(default_ext_path)) != 0:
        logger.warning(
            "You are using a custom extensions path, "
            + "but the default extensions directory is not empty. "
            + f"Please clean-up the '{default_ext_path}' directory."
        )
        logger.warning(
            f"You can move the existing '{default_ext_path}' directory to: "
            + f" '{settings.lnbits_extensions_path}/extensions'"
        )

    sys.path.append(str(Path(settings.lnbits_extensions_path, "extensions")))
    sys.path.append(str(Path(settings.lnbits_extensions_path, "upgrades")))


def register_new_ext_routes(app: FastAPI) -> Callable:
    # Returns a function that registers new routes for an extension.
    # The returned function encapsulates (creates a closure around)
    # the `app` object but does expose it.
    def register_new_ext_routes_fn(ext: Extension):
        register_ext_routes(app, ext)

    return register_new_ext_routes_fn


def register_new_ratelimiter(app: FastAPI) -> Callable:
    def register_new_ratelimiter_fn():
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[
                f"{settings.lnbits_rate_limit_no}/{settings.lnbits_rate_limit_unit}"
            ],
        )
        app.state.limiter = limiter

    return register_new_ratelimiter_fn


def register_ext_routes(app: FastAPI, ext: Extension) -> None:
    """Register FastAPI routes for extension."""
    ext_module = importlib.import_module(ext.module_name)

    ext_route = getattr(ext_module, f"{ext.code}_ext")

    if hasattr(ext_module, f"{ext.code}_start"):
        ext_start_func = getattr(ext_module, f"{ext.code}_start")
        ext_start_func()

    if hasattr(ext_module, f"{ext.code}_static_files"):
        ext_statics = getattr(ext_module, f"{ext.code}_static_files")
        for s in ext_statics:
            static_dir = Path(
                settings.lnbits_extensions_path, "extensions", *s["path"].split("/")
            )
            app.mount(s["path"], StaticFiles(directory=static_dir), s["name"])

    if hasattr(ext_module, f"{ext.code}_redirect_paths"):
        ext_redirects = getattr(ext_module, f"{ext.code}_redirect_paths")
        settings.lnbits_extensions_redirects = [
            r for r in settings.lnbits_extensions_redirects if r["ext_id"] != ext.code
        ]
        for r in ext_redirects:
            r["ext_id"] = ext.code
            settings.lnbits_extensions_redirects.append(r)

    logger.trace(f"adding route for extension {ext_module}")

    prefix = f"/upgrades/{ext.upgrade_hash}" if ext.upgrade_hash != "" else ""
    app.include_router(router=ext_route, prefix=prefix)


def register_startup(app: FastAPI):
    @app.on_event("startup")
    async def lnbits_startup():
        try:
            # wait till migration is done
            await migrate_databases()

            # setup admin settings
            await check_admin_settings()
            await check_webpush_settings()

            log_server_info()

            # initialize WALLET
            try:
                set_wallet_class()
            except Exception as e:
                logger.error(
                    f"Error initializing {settings.lnbits_backend_wallet_class}: "
                    f"{str(e)}"
                )
                set_void_wallet_class()

            # initialize funding source
            await check_funding_source()

            # check extensions after restart
            await check_installed_extensions(app)

            if settings.lnbits_admin_ui:
                initialize_server_logger()

        except Exception as e:
            logger.error(str(e))
            raise ImportError("Failed to run 'startup' event.")


def register_shutdown(app: FastAPI):
    @app.on_event("shutdown")
    async def on_shutdown():
        cancel_all_tasks()
        # wait a bit to allow them to finish, so that cleanup can run without problems
        await asyncio.sleep(0.1)
        WALLET = get_wallet_class()
        await WALLET.cleanup()


def initialize_server_logger():
    super_user_hash = sha256(settings.super_user.encode("utf-8")).hexdigest()

    serverlog_queue = asyncio.Queue()

    async def update_websocket_serverlog():
        while True:
            msg = await serverlog_queue.get()
            await websocketUpdater(super_user_hash, msg)

    create_permanent_task(update_websocket_serverlog)

    logger.add(
        lambda msg: serverlog_queue.put_nowait(msg),
        format=Formatter().format,
    )


def log_server_info():
    logger.info("Starting LNbits")
    logger.info(f"Version: {settings.version}")
    logger.info(f"Baseurl: {settings.lnbits_baseurl}")
    logger.info(f"Host: {settings.host}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"Debug: {settings.debug}")
    logger.info(f"Site title: {settings.lnbits_site_title}")
    logger.info(f"Funding source: {settings.lnbits_backend_wallet_class}")
    logger.info(f"Data folder: {settings.lnbits_data_folder}")
    logger.info(f"Database: {get_db_vendor_name()}")
    logger.info(f"Service fee: {settings.lnbits_service_fee}")


def get_db_vendor_name():
    db_url = settings.lnbits_database_url
    return (
        "PostgreSQL"
        if db_url and db_url.startswith("postgres://")
        else (
            "CockroachDB"
            if db_url and db_url.startswith("cockroachdb://")
            else "SQLite"
        )
    )


def register_async_tasks(app):
    @app.route("/wallet/webhook")
    async def webhook_listener():
        return await webhook_handler()

    @app.on_event("startup")
    async def listeners():
        create_permanent_task(check_pending_payments)
        create_permanent_task(invoice_listener)
        create_permanent_task(internal_invoice_listener)
        create_permanent_task(cache.invalidate_forever)
        register_task_listeners()
        register_killswitch()
        # await run_deferred_async() # calle: doesn't do anyting?


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
    logger.add(sys.stdout, level=log_level, format=formatter.format)
    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.error").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.error").propagate = False


class Formatter:
    def __init__(self):
        self.padding = 0
        self.minimal_fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | <level>{level}</level> | "
            "<level>{message}</level>\n"
        )
        if settings.debug:
            self.fmt = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | "
                "<level>{level: <4}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>\n"
            )
        else:
            self.fmt = self.minimal_fmt

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
