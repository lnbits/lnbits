import os

from .wallets import LntxbotWallet  # OR LndHubWallet


WALLET = LntxbotWallet(
    endpoint=os.getenv("LNTXBOT_API_ENDPOINT"),
    admin_key=os.getenv("LNTXBOT_ADMIN_KEY"),
    invoice_key=os.getenv("LNTXBOT_INVOICE_KEY"),
)

# OR
# WALLET = LndHubWallet(uri=os.getenv("LNDHUB_URI"))

LNBITS_PATH = os.path.dirname(os.path.realpath(__file__))
DATABASE_PATH = os.getenv("DATABASE_PATH") or os.path.join(LNBITS_PATH, "data", "database.sqlite3")
DEFAULT_USER_WALLET_NAME = os.getenv("DEFAULT_USER_WALLET_NAME") or "Bitcoin LN Wallet"
