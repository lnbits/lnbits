from enum import Enum


class WalletType(str, Enum):
    """Wallet types. Onchain and Liquid are reserved and cannot be created yet."""

    LIGHTNING = "lightning"
    FIAT = "fiat"
    RECEIVE_ONLY = "fiat"  # Compatibility with the receive-only development name.
    ONCHAIN = "onchain"
    LIQUID = "liquid"
    LIGHTNING_SHARED = "lightning-shared"

    @classmethod
    def _missing_(cls, value):
        if value == "receive-only":
            return cls.FIAT
        return None
