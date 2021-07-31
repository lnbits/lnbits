import sys
import warnings
import importlib
import traceback

from quart import g
from quart_trio import QuartTrio
from quart_cors import cors  # type: ignore
from quart_compress import Compress  # type: ignore

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


def create_app(config_object="lnbits.settings") -> QuartTrio:
    """Create application factory.
    :param config_object: The configuration object to use.
    """
    app = QuartTrio(__name__, static_folder="static")
    app.config.from_object(config_object)
    app.asgi_http_class = ASGIProxyFix

    cors(app)
    Compress(app)

    check_funding_source(app)
    register_assets(app)
    register_blueprints(app)
    register_filters(app)
    register_commands(app)
    register_async_tasks(app)
    register_exception_handlers(app)

    return app


def check_funding_source(app: QuartTrio) -> None:
    @app.before_serving
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


def register_blueprints(app: QuartTrio) -> None:
    """Register Flask blueprints / LNbits extensions."""
    app.register_blueprint(core_app)

    for ext in get_valid_extensions():
        try:
            ext_module = importlib.import_module(f"lnbits.extensions.{ext.code}")
            bp = getattr(ext_module, f"{ext.code}_ext")

            app.register_blueprint(bp, url_prefix=f"/{ext.code}")
        except Exception:
            raise ImportError(
                f"Please make sure that the extension `{ext.code}` follows conventions."
            )


def register_commands(app: QuartTrio):
    """Register Click commands."""
    app.cli.add_command(db_migrate)
    app.cli.add_command(handle_assets)


def register_assets(app: QuartTrio):
    """Serve each vendored asset separately or a bundle."""

    @app.before_request
    async def vendored_assets_variable():
        if app.config["DEBUG"]:
            g.VENDORED_JS = map(url_for_vendored, get_js_vendored())
            g.VENDORED_CSS = map(url_for_vendored, get_css_vendored())
        else:
            g.VENDORED_JS = ["/static/bundle.js"]
            g.VENDORED_CSS = ["/static/bundle.css"]


def register_filters(app: QuartTrio):
    """Jinja filters."""
    app.jinja_env.globals["SITE_TITLE"] = app.config["LNBITS_SITE_TITLE"]
    app.jinja_env.globals["SITE_TAGLINE"] = app.config["LNBITS_SITE_TAGLINE"]
    app.jinja_env.globals["SITE_DESCRIPTION"] = app.config["LNBITS_SITE_DESCRIPTION"]
    app.jinja_env.globals["LNBITS_THEME_OPTIONS"] = app.config["LNBITS_THEME_OPTIONS"]
    app.jinja_env.globals["LNBITS_VERSION"] = app.config["LNBITS_COMMIT"]
    app.jinja_env.globals["EXTENSIONS"] = get_valid_extensions()


def register_async_tasks(app):
    @app.route("/wallet/webhook", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def webhook_listener():
        return await webhook_handler()

    @app.before_serving
    async def listeners():
        run_deferred_async()
        app.nursery.start_soon(catch_everything_and_restart, check_pending_payments)
        app.nursery.start_soon(catch_everything_and_restart, invoice_listener)
        app.nursery.start_soon(catch_everything_and_restart, internal_invoice_listener)

    @app.after_serving
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
