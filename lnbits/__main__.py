from .app import create_app
from .commands import migrate_databases, transpile_scss, bundle_vendored

migrate_databases()
transpile_scss()
bundle_vendored()

app = create_app()
app.run(host=app.config["HOST"], port=app.config["PORT"])
