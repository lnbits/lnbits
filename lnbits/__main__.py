from .app import create_app
from .commands import migrate_databases


migrate_databases()

app = create_app()
app.run(host=app.config["HOST"], port=app.config["PORT"])
