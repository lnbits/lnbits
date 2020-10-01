import importlib
from typing import List
from lnbits.core.crud import get_admin

admin = get_admin()

wallet_class = admin.funding_source

ENV = "production"
DEBUG = ENV == "development"

LNBITS_PATH = path.dirname(path.realpath(__file__))
LNBITS_DATA_FOLDER = admin.data_folder
LNBITS_ALLOWED_USERS: List[str] = admin.allowed_users
LNBITS_ADMIN_USERS: List[str] = admin.user
LNBITS_DISABLED_EXTENSIONS: List[str] = admin.disabled_ext
LNBITS_SITE_TITLE = admin.site_title

WALLET = wallet_class()
DEFAULT_WALLET_NAME = admin.default_wallet_name
FORCE_HTTPS = admin.force_https
SERVICE_FEE = admin.service_fee
