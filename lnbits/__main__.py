import trio

from .commands import migrate_databases, transpile_scss, bundle_vendored

trio.run(migrate_databases)
transpile_scss()
bundle_vendored()

from .app import create_app

app = create_app()

from .settings import (
    LNBITS_SITE_TITLE,
    SERVICE_FEE,
    DEBUG,
    LNBITS_DATA_FOLDER,
    WALLET,
    LNBITS_COMMIT,
)

print(
    f"""Starting LNbits with
  - git version: {LNBITS_COMMIT}
  - site title: {LNBITS_SITE_TITLE}
  - debug: {DEBUG}
  - data folder: {LNBITS_DATA_FOLDER}
  - funding source: {WALLET.__class__.__name__}
  - service fee: {SERVICE_FEE}
"""
)

app.run(host=app.config["HOST"], port=app.config["PORT"])
