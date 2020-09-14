import importlib

from flask import Flask, g
from flask_assets import Bundle  # type: ignore
from flask_cors import CORS  # type: ignore
from flask_talisman import Talisman  # type: ignore
from werkzeug.middleware.proxy_fix import ProxyFix

from .commands import flask_migrate
from .core import core_app
from .db import open_db
from .ext import assets, compress
from .helpers import get_valid_extensions


def create_app(config_object="lnbits.settings") -> Flask:
    """Create application factory, as explained here: http://flask.pocoo.org/docs/patterns/appfactories/.
    :param config_object: The configuration object to use.
    """
    app = Flask(__name__, static_folder="static")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # type: ignore
    app.config.from_object(config_object)

    register_flask_extensions(app)
    register_blueprints(app)
    register_filters(app)
    register_commands(app)
    register_request_hooks(app)

    return app


def register_blueprints(app) -> None:
    """Register Flask blueprints / LNbits extensions."""
    app.register_blueprint(core_app)

    for ext in get_valid_extensions():
        try:
            ext_module = importlib.import_module(f"lnbits.extensions.{ext.code}")
            app.register_blueprint(getattr(ext_module, f"{ext.code}_ext"), url_prefix=f"/{ext.code}")
        except Exception:
            raise ImportError(f"Please make sure that the extension `{ext.code}` follows conventions.")


def register_commands(app):
    """Register Click commands."""
    app.cli.add_command(flask_migrate)


def register_flask_extensions(app):
    """Register Flask extensions."""
    """If possible we use the .init_app() option so that Blueprints can also use extensions."""
    CORS(app)
    Talisman(
        app,
        force_https=app.config["FORCE_HTTPS"],
        content_security_policy={
            "default-src": [
                "'self'",
                "'unsafe-eval'",
                "'unsafe-inline'",
                "blob:",
                "api.opennode.co",
            ]
        },
    )

    assets.init_app(app)
    assets.register("base_css", Bundle("scss/base.scss", filters="pyscss", output="css/base.css"))
    compress.init_app(app)


def register_filters(app):
    """Jinja filters."""
    app.jinja_env.globals["DEBUG"] = app.config["DEBUG"]
    app.jinja_env.globals["EXTENSIONS"] = get_valid_extensions()
    app.jinja_env.globals["SITE_TITLE"] = app.config["LNBITS_SITE_TITLE"]


def register_request_hooks(app):
    """Open the core db for each request so everything happens in a big transaction"""

    @app.before_request
    def before_request():
        g.db = open_db()

    @app.teardown_request
    def after_request(exc):
        g.db.__exit__(type(exc), exc, None)
