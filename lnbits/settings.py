import importlib
import os


wallets_module = importlib.import_module("lnbits.wallets")
wallet_class = getattr(wallets_module, os.getenv("LNBITS_BACKEND_WALLET_CLASS", "VoidWallet"))

LNBITS_PATH = os.path.dirname(os.path.realpath(__file__))
LNBITS_DATA_FOLDER = os.getenv("LNBITS_DATA_FOLDER", os.path.join(LNBITS_PATH, "data"))

WALLET = wallet_class()
DEFAULT_WALLET_NAME = os.getenv("LNBITS_DEFAULT_WALLET_NAME", "LNbits wallet")
FORCE_HTTPS = os.getenv("LNBITS_FORCE_HTTPS", "1") == "1"
SERVICE_FEE = float(os.getenv("LNBITS_SERVICE_FEE", "0.0"))
