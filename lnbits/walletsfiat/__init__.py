from __future__ import annotations

import importlib
from enum import Enum

from loguru import logger

from lnbits.settings import settings
from lnbits.walletsfiat.base import FiatWallet

from .stripe import StripeWallet

fiat_wallets_module = importlib.import_module("lnbits.walletsfiat")


def get_fiat_provider(name: str) -> FiatWallet | None:
    if name not in fiat_providers:
        return None
    return fiat_providers[name]


class FiatProvider(Enum):
    stripe = "StripeWallet"


def init_fiat_providers():
    """Initialize fiat providers."""
    for fiat_provider in FiatProvider:
        # todo: why called twice
        global fiat_providers
        if fiat_providers.get(fiat_provider.name):
            continue
        fiat_providers[fiat_provider.name] = init_fiat_provider(fiat_provider)


def init_fiat_provider(fiat_provider: FiatProvider) -> FiatWallet | None:
    """Initialize a specific fiat provider."""
    try:
        if not settings.is_fiat_provider_enabled(fiat_provider.name):
            logger.debug(f"Fiat provider '{fiat_provider.name}' not enabled.")
            return None
        provider_constructor = getattr(fiat_wallets_module, fiat_provider.value)
        return provider_constructor()
    except Exception as e:
        logger.warning(
            f"Failed to initialize fiat provider '{fiat_provider.name}': {e}"
        )
        return None


fiat_providers: dict[str, FiatWallet | None] = {}

init_fiat_providers()

__all__ = [
    "StripeWallet",
]
