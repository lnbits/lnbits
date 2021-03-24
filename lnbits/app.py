import importlib
import warnings

from quart import g
from quart_trio import QuartTrio
from quart_cors import cors  # type: ignore
from quart_compress import Compress  # type: ignore
from secure import SecureHeaders  # type: ignore

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
    run_deferred_async,
    check_pending_payments,
    invoice_listener,
    internal_invoice_listener,
    webhook_handler,
    grab_app_for_later,
)
from .settings import WALLET

secure_headers = SecureHeaders(hsts=False, xfo=False)


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
    register_request_hooks(app)
    register_async_tasks(app)
    grab_app_for_later(app)

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

            @bp.teardown_request
            async def after_request(exc):
                await ext_module.db.close_session()

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
    app.jinja_env.globals["EXTENSIONS"] = get_valid_extensions()


def register_request_hooks(app: QuartTrio):
    """Open the core db for each request so everything happens in a big transaction"""

    @app.before_request
    async def before_request():
        g.nursery = app.nursery

    @app.teardown_request
    async def after_request(exc):
        from lnbits.core import db

        await db.close_session()

    @app.after_request
    async def set_secure_headers(response):
        secure_headers.quart(response)
        return response


def register_async_tasks(app):
    @app.route("/wallet/webhook", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def webhook_listener():
        return await webhook_handler()

    @app.before_serving
    async def listeners():
        run_deferred_async(app.nursery)
        app.nursery.start_soon(check_pending_payments)
        app.nursery.start_soon(invoice_listener, app.nursery)
        app.nursery.start_soon(internal_invoice_listener, app.nursery)

    @app.after_serving
    async def stop_listeners():
        pass
