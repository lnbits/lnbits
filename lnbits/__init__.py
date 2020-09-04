import re
import importlib
import sqlite3

from flask import Flask
from flask_assets import Environment, Bundle  # type: ignore
from flask_compress import Compress  # type: ignore
from flask_cors import CORS  # type: ignore
from flask_talisman import Talisman  # type: ignore
from os import getenv
from werkzeug.middleware.proxy_fix import ProxyFix

from .core import core_app
from .helpers import ExtensionManager
from .settings import FORCE_HTTPS
from .db import open_db, open_ext_db


disabled_extensions = getenv("LNBITS_DISABLED_EXTENSIONS", "").split(",")

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # type: ignore
valid_extensions = [ext for ext in ExtensionManager(disabled=disabled_extensions).extensions if ext.is_valid]


# optimization & security
# -----------------------

Compress(app)
CORS(app)
Talisman(
    app,
    force_https=FORCE_HTTPS,
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


# blueprints / extensions
# -----------------------

app.register_blueprint(core_app)

for ext in valid_extensions:
    try:
        ext_module = importlib.import_module(f"lnbits.extensions.{ext.code}")
        app.register_blueprint(getattr(ext_module, f"{ext.code}_ext"), url_prefix=f"/{ext.code}")
    except Exception:
        raise ImportError(f"Please make sure that the extension `{ext.code}` follows conventions.")


# filters
# -------

app.jinja_env.globals["DEBUG"] = app.config["DEBUG"]
app.jinja_env.globals["EXTENSIONS"] = valid_extensions
app.jinja_env.globals["SITE_TITLE"] = getenv("LNBITS_SITE_TITLE", "LNbits")


# assets
# ------

assets = Environment(app)
assets.url = app.static_url_path
assets.register("base_css", Bundle("scss/base.scss", filters="pyscss", output="css/base.css"))


# commands
# --------


def migrate_databases():
    """Creates the necessary databases if they don't exist already; or migrates them."""

    from .core import migrations as core_migrations

    with open_db() as core_db:
        try:
            rows = core_db.fetchall("SELECT * FROM dbversions")
        except sqlite3.OperationalError:
            # migration 3 wasn't ran
            core_migrations.m000_create_migrations_table(core_db)
            rows = core_db.fetchall("SELECT * FROM dbversions")

        current_versions = {row["db"]: row["version"] for row in rows}
        matcher = re.compile(r"^m(\d\d\d)_")

        def run_migration(db, migrations_module):
            db_name = migrations_module.__name__.split(".")[-2]
            for key, run_migration in migrations_module.__dict__.items():
                if match := matcher.match(key):
                    version = int(match.group(1))
                    if version > current_versions.get(db_name, 0):
                        print(f"running migration {db_name}.{version}")
                        run_migration(db)
                        core_db.execute(
                            "INSERT OR REPLACE INTO dbversions (db, version) VALUES (?, ?)", (db_name, version)
                        )

        run_migration(core_db, core_migrations)

        for ext in valid_extensions:
            try:
                ext_migrations = importlib.import_module(f"lnbits.extensions.{ext.code}.migrations")
                with open_ext_db(ext.code) as db:
                    run_migration(db, ext_migrations)
            except ImportError:
                raise ImportError(f"Please make sure that the extension `{ext.code}` has a migrations file.")
