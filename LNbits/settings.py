import os

INVOICE_KEY = os.getenv("INVOICE_KEY")
ADMIN_KEY = os.getenv("ADMIN_KEY")
API_ENDPOINT = os.getenv("API_ENDPOINT")

LNBITS_PATH = os.path.dirname(os.path.realpath(__file__))
DATABASE_PATH= os.getenv("DATABASE_PATH") or os.path.join(LNBITS_PATH, "data", "database.sqlite3")
