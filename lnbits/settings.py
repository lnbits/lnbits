import importlib
import subprocess
from os import path
from typing import List

from environs import Env  # type: ignore

env = Env()
env.read_env()

wallets_module = importlib.import_module("lnbits.wallets")
wallet_class = getattr(
    wallets_module, env.str("LNBITS_BACKEND_WALLET_CLASS", default="VoidWallet")
)

DEBUG = env.bool("DEBUG", default=False)

HOST = env.str("HOST", default="127.0.0.1")
PORT = env.int("PORT", default=5000)

LNBITS_PATH = path.dirname(path.realpath(__file__))
LNBITS_DATA_FOLDER = env.str(
    "LNBITS_DATA_FOLDER", default=path.join(LNBITS_PATH, "data")
)
LNBITS_DATABASE_URL = env.str("LNBITS_DATABASE_URL", default=None)

LNBITS_ALLOWED_USERS: List[str] = env.list(
    "LNBITS_ALLOWED_USERS", default=[], subcast=str
)
LNBITS_ADMIN_USERS: List[str] = env.list("LNBITS_ADMIN_USERS", default=[], subcast=str)
LNBITS_ADMIN_EXTENSIONS: List[str] = env.list(
    "LNBITS_ADMIN_EXTENSIONS", default=[], subcast=str
)
LNBITS_DISABLED_EXTENSIONS: List[str] = env.list(
    "LNBITS_DISABLED_EXTENSIONS", default=[], subcast=str
)

LNBITS_AD_SPACE = env.list("LNBITS_AD_SPACE", default=[])
LNBITS_HIDE_API = env.bool("LNBITS_HIDE_API", default=False)
LNBITS_SITE_TITLE = env.str("LNBITS_SITE_TITLE", default="LNbits")
LNBITS_DENOMINATION = env.str("LNBITS_DENOMINATION", default="sats")
LNBITS_SITE_TAGLINE = env.str(
    "LNBITS_SITE_TAGLINE", default="free and open-source lightning wallet"
)
LNBITS_SITE_DESCRIPTION = env.str("LNBITS_SITE_DESCRIPTION", default="")
LNBITS_THEME_OPTIONS: List[str] = env.list(
    "LNBITS_THEME_OPTIONS",
    default="classic, flamingo, mint, salvador, monochrome, autumn",
    subcast=str,
)
LNBITS_CUSTOM_LOGO = env.str("LNBITS_CUSTOM_LOGO", default="")

WALLET = wallet_class()
FAKE_WALLET = getattr(wallets_module, "FakeWallet")()
DEFAULT_WALLET_NAME = env.str("LNBITS_DEFAULT_WALLET_NAME", default="LNbits wallet")
PREFER_SECURE_URLS = env.bool("LNBITS_FORCE_HTTPS", default=True)

RESERVE_FEE_MIN = env.int("LNBITS_RESERVE_FEE_MIN", default=2000)
RESERVE_FEE_PERCENT = env.float("LNBITS_RESERVE_FEE_PERCENT", default=1.0)
SERVICE_FEE = env.float("LNBITS_SERVICE_FEE", default=0.0)

try:
    LNBITS_COMMIT = (
        subprocess.check_output(
            ["git", "-C", LNBITS_PATH, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        )
        .strip()
        .decode("ascii")
    )
except:
    LNBITS_COMMIT = "unknown"
