import importlib

from environs import Env  # type: ignore
from os import path
from typing import List


env = Env()
env.read_env()

wallets_module = importlib.import_module("lnbits.wallets")
wallet_class = getattr(wallets_module, env.str("LNBITS_BACKEND_WALLET_CLASS", default="VoidWallet"))

ENV = env.str("FLASK_ENV", default="production")
DEBUG = ENV == "development"

LNBITS_PATH = path.dirname(path.realpath(__file__))
LNBITS_DATA_FOLDER = env.str("LNBITS_DATA_FOLDER", default=path.join(LNBITS_PATH, "data"))
LNBITS_ALLOWED_USERS: List[str] = env.list("LNBITS_ALLOWED_USERS", default=[], subcast=str)
LNBITS_DISABLED_EXTENSIONS: List[str] = env.list("LNBITS_DISABLED_EXTENSIONS", default=[], subcast=str)
LNBITS_SITE_TITLE = env.str("LNBITS_SITE_TITLE", default="LNbits")

WALLET = wallet_class()
DEFAULT_WALLET_NAME = env.str("LNBITS_DEFAULT_WALLET_NAME", default="LNbits wallet")
FORCE_HTTPS = env.bool("LNBITS_FORCE_HTTPS", default=True)
SERVICE_FEE = env.float("LNBITS_SERVICE_FEE", default=0.0)
