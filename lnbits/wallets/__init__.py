from __future__ import annotations

# flake8: noqa: F401
import importlib
from typing import Optional

from lnbits.settings import settings
from lnbits.wallets.base import Wallet

from .cliche import ClicheWallet
from .cln import CoreLightningWallet
from .cln import CoreLightningWallet as CLightningWallet
from .clnrest import CLNRestWallet
from .eclair import EclairWallet
from .fake import FakeWallet
from .lnbits import LNbitsWallet
from .lndgrpc import LndWallet
from .lndrest import LndRestWallet
from .lnpay import LNPayWallet
from .lntips import LnTipsWallet
from .opennode import OpenNodeWallet
from .spark import SparkWallet
from .void import VoidWallet


def set_wallet_class(class_name: Optional[str] = None):
    backend_wallet_class = class_name or settings.lnbits_backend_wallet_class
    wallet_class = getattr(wallets_module, backend_wallet_class)
    global WALLET
    WALLET = wallet_class()


def get_wallet_class() -> Wallet:
    return WALLET


wallets_module = importlib.import_module("lnbits.wallets")
FAKE_WALLET = FakeWallet()

# initialize as fake wallet
WALLET: Wallet = FAKE_WALLET
