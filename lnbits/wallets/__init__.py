from __future__ import annotations

import importlib
from typing import Optional

from lnbits.nodes import set_node_class
from lnbits.settings import settings
from lnbits.wallets.base import Wallet

from .alby import AlbyWallet
from .breez import BreezSdkWallet
from .cliche import ClicheWallet
from .corelightning import CoreLightningWallet

# The following import is intentional to keep backwards compatibility
# for old configs that called it CLightningWallet. Do not remove.
from .corelightning import CoreLightningWallet as CLightningWallet
from .corelightningrest import CoreLightningRestWallet
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
from .zbd import ZBDWallet


def set_wallet_class(class_name: Optional[str] = None):
    backend_wallet_class = class_name or settings.lnbits_backend_wallet_class
    wallet_class = getattr(wallets_module, backend_wallet_class)
    global WALLET
    WALLET = wallet_class()
    if WALLET.__node_cls__:
        set_node_class(WALLET.__node_cls__(WALLET))


def get_wallet_class() -> Wallet:
    return WALLET


wallets_module = importlib.import_module("lnbits.wallets")
FAKE_WALLET = FakeWallet()

# initialize as fake wallet
WALLET: Wallet = FAKE_WALLET
