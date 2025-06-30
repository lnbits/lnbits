from __future__ import annotations

import importlib
from enum import Enum

from lnbits.fiat.base import FiatProvider
from lnbits.settings import settings

from .stripe import StripeWallet

fiat_module = importlib.import_module("lnbits.fiat")


class FiatProviderType(Enum):
    stripe = "StripeWallet"


async def get_fiat_provider(name: str) -> FiatProvider:
    if name not in FiatProviderType.__members__:
        raise ValueError(f"Fiat provider '{name}' is not supported.")

    fiat_provider = fiat_providers.get(name)
    if fiat_provider:
        status = await fiat_provider.status(only_check_settings=True)
        if status.error_message:
            await fiat_provider.cleanup()
            del fiat_providers[name]
        else:
            return fiat_provider
    fiat_providers[name] = _init_fiat_provider(FiatProviderType[name])
    return fiat_providers[name]


def _init_fiat_provider(fiat_provider: FiatProviderType) -> FiatProvider:
    if not settings.is_fiat_provider_enabled(fiat_provider.name):
        raise ValueError(f"Fiat provider '{fiat_provider.name}' not enabled.")
    provider_constructor = getattr(fiat_module, fiat_provider.value)
    return provider_constructor()


fiat_providers: dict[str, FiatProvider] = {}


__all__ = [
    "StripeWallet",
]
