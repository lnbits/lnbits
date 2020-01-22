import os

from .wallets import LntxbotWallet  # OR LndWallet OR OpennodeWallet
 
#WALLET = OpenNodeWallet(endpoint=os.getenv("OPENNODE_API_ENDPOINT"),admin_key=os.getenv("OPENNODE_ADMIN_KEY"),invoice_key=os.getenv("OPENNODE_INVOICE_KEY"))
WALLET = LntxbotWallet(endpoint=os.getenv("LNTXBOT_API_ENDPOINT"),admin_key=os.getenv("LNTXBOT_ADMIN_KEY"),invoice_key=os.getenv("LNTXBOT_INVOICE_KEY"))
#WALLET = LndWallet(endpoint=os.getenv("LND_API_ENDPOINT"),admin_macaroon=os.getenv("LND_ADMIN_MACAROON"),invoice_macaroon=os.getenv("LND_INVOICE_MACAROON"),read_macaroon=os.getenv("LND_READ_MACAROON"))
#WALLET = LNPayWallet(endpoint=os.getenv("LNPAY_API_ENDPOINT"),admin_key=os.getenv("LNPAY_ADMIN_KEY"),invoice_key=os.getenv("LNPAY_INVOICE_KEY"),api_key=os.getenv("LNPAY_API_KEY"),read_key=os.getenv("LNPAY_READ_KEY"))


LNBITS_PATH = os.path.dirname(os.path.realpath(__file__))
DATABASE_PATH = os.getenv("DATABASE_PATH") or os.path.join(LNBITS_PATH, "data", "database.sqlite3")
DEFAULT_USER_WALLET_NAME = os.getenv("DEFAULT_USER_WALLET_NAME") or "Bitcoin LN Wallet"

FEE_RESERVE = float(os.getenv("FEE_RESERVE") or 0)
