from __future__ import annotations

import importlib
from typing import Optional

from lnbits.nodes import set_node_class
from lnbits.settings import settings
from lnbits.wallets.base import Wallet

from .alby import AlbyWallet
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
    wallet_class_constructor = getattr(wallets_module, backend_wallet_class)
    global wallet_class
    wallet_class = wallet_class_constructor()
    if wallet_class.__node_cls__:
        set_node_class(wallet_class.__node_cls__(wallet_class))


def get_wallet_class() -> Wallet:
    return wallet_class


wallets_module = importlib.import_module("lnbits.wallets")
fake_wallet = FakeWallet()

# initialize as fake wallet
wallet_class: Wallet = fake_wallet
