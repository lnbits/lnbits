import importlib
import os


wallets_module = importlib.import_module("lnbits.wallets")
wallet_class = getattr(wallets_module, os.getenv("LNBITS_BACKEND_WALLET_CLASS", "LntxbotWallet"))

LNBITS_PATH = os.path.dirname(os.path.realpath(__file__))
LNBITS_DATA_FOLDER = os.getenv("LNBITS_DATA_FOLDER", os.path.join(LNBITS_PATH, "data"))

WALLET = wallet_class()
DEFAULT_WALLET_NAME = os.getenv("LNBITS_DEFAULT_WALLET_NAME", "LNbits wallet")
FEE_RESERVE = float(os.getenv("LNBITS_FEE_RESERVE", 0))
