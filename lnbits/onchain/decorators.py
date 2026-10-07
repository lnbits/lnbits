from dataclasses import dataclass

from fastapi import Depends, HTTPException

from lnbits.core.models.wallets import WalletTypeInfo
from lnbits.decorators import require_admin_key, require_invoice_key


@dataclass(frozen=True)
class OnchainAuth:
    wallet_id: str


def _scope(info: WalletTypeInfo) -> OnchainAuth:
    if not info.wallet.is_onchain_wallet:
        raise HTTPException(403, "An onchain wallet key is required")
    return OnchainAuth(wallet_id=info.wallet.id)


async def require_onchain_read(
    info: WalletTypeInfo = Depends(require_invoice_key),
) -> OnchainAuth:
    return _scope(info)


async def require_onchain_admin(
    info: WalletTypeInfo = Depends(require_admin_key),
) -> OnchainAuth:
    return _scope(info)
