from .app import create_app
from .commands import migrate_databases


migrate_databases()

app = create_app()
app.run()
