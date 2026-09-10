from dataclasses import dataclass
from enum import Enum


class WalletType(str, Enum):
    """The payment capabilities and settlement type of a wallet.

    ``LIGHTNING_SHARED`` is retained as an internal compatibility type for wallet
    sharing. New wallet types should be registered in ``WALLET_TYPE_CAPABILITIES``
    before they are enabled for creation.
    """

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


@dataclass(frozen=True)
class WalletTypeCapabilities:
    creatable: bool
    receives: bool
    sends: bool
    shareable: bool = False
    lightning_address: bool = False
    default_icon: str = "flash_on"


WALLET_TYPE_CAPABILITIES: dict[WalletType, WalletTypeCapabilities] = {
    WalletType.LIGHTNING: WalletTypeCapabilities(
        creatable=True,
        receives=True,
        sends=True,
        shareable=True,
        lightning_address=True,
    ),
    WalletType.FIAT: WalletTypeCapabilities(
        creatable=True,
        receives=True,
        sends=False,
        default_icon="credit_card",
    ),
    # Registered placeholders. Enabling either type requires its payment service.
    WalletType.ONCHAIN: WalletTypeCapabilities(
        creatable=False,
        receives=False,
        sends=False,
    ),
    WalletType.LIQUID: WalletTypeCapabilities(
        creatable=False,
        receives=False,
        sends=False,
    ),
    # Shared wallets are created only through the invitation workflow. Their
    # effective receive/send capabilities are intersected with share permissions.
    WalletType.LIGHTNING_SHARED: WalletTypeCapabilities(
        creatable=False,
        receives=True,
        sends=True,
    ),
}


def wallet_type_capabilities(wallet_type: WalletType) -> WalletTypeCapabilities:
    return WALLET_TYPE_CAPABILITIES[wallet_type]
