import importlib

from quart import Quart, g
from quart_cors import cors  # type: ignore
from quart_compress import Compress  # type: ignore
from secure import SecureHeaders  # type: ignore

from .commands import db_migrate
from .core import core_app
from .db import open_db
from .helpers import get_valid_extensions, get_js_vendored, get_css_vendored, url_for_vendored
from .proxy_fix import ProxyFix

secure_headers = SecureHeaders(hsts=False)


def create_app(config_object="lnbits.settings") -> Quart:
    """Create application factory.
    :param config_object: The configuration object to use.
    """
    app = Quart(__name__, static_folder="static")
    app.config.from_object(config_object)

    cors(app)
    Compress(app)
    ProxyFix(app, x_proto=1, x_host=1)

    register_assets(app)
    register_blueprints(app)
    register_filters(app)
    register_commands(app)
    register_request_hooks(app)

    return app


def register_blueprints(app: Quart) -> None:
    """Register Flask blueprints / LNbits extensions."""
    app.register_blueprint(core_app)

    for ext in get_valid_extensions():
        try:
            ext_module = importlib.import_module(f"lnbits.extensions.{ext.code}")
            app.register_blueprint(getattr(ext_module, f"{ext.code}_ext"), url_prefix=f"/{ext.code}")
        except Exception:
            raise ImportError(f"Please make sure that the extension `{ext.code}` follows conventions.")


def register_commands(app: Quart):
    """Register Click commands."""
    app.cli.add_command(db_migrate)


def register_assets(app: Quart):
    """Serve each vendored asset separately or a bundle."""

    @app.before_request
    async def vendored_assets_variable():
        if app.config["DEBUG"]:
            g.VENDORED_JS = map(url_for_vendored, get_js_vendored())
            g.VENDORED_CSS = map(url_for_vendored, get_css_vendored())
        else:
            g.VENDORED_JS = ["/static/bundle.js"]
            g.VENDORED_CSS = ["/static/bundle.css"]


def register_filters(app: Quart):
    """Jinja filters."""
    app.jinja_env.globals["SITE_TITLE"] = app.config["LNBITS_SITE_TITLE"]
    app.jinja_env.globals["EXTENSIONS"] = get_valid_extensions()


def register_request_hooks(app: Quart):
    """Open the core db for each request so everything happens in a big transaction"""

    @app.before_request
    async def before_request():
        g.db = open_db()

    @app.after_request
    async def set_secure_headers(response):
        secure_headers.quart(response)
        return response

    @app.teardown_request
    async def after_request(exc):
        g.db.__exit__(type(exc), exc, None)
