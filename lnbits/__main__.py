from .app import create_app
from .commands import migrate_databases, transpile_scss, bundle_vendored
from .settings import LNBITS_SITE_TITLE, SERVICE_FEE, DEBUG, LNBITS_DATA_FOLDER, WALLET

migrate_databases()
transpile_scss()
bundle_vendored()

app = create_app()

print(
    f"""Starting LNbits with
  - site title: {LNBITS_SITE_TITLE}
  - debug: {DEBUG}
  - data folder: {LNBITS_DATA_FOLDER}
  - funding source: {WALLET.__class__.__name__}
  - service fee: {SERVICE_FEE}
"""
)

app.run(host=app.config["HOST"], port=app.config["PORT"])
