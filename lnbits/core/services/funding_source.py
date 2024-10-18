from lnbits.settings import settings
from lnbits.wallets import get_funding_source, set_funding_source

from ..crud import get_total_balance
from ..models import BalanceDelta


async def switch_to_voidwallet() -> None:
    funding_source = get_funding_source()
    if funding_source.__class__.__name__ == "VoidWallet":
        return
    set_funding_source("VoidWallet")
    settings.lnbits_backend_wallet_class = "VoidWallet"


async def get_balance_delta() -> BalanceDelta:
    funding_source = get_funding_source()
    status = await funding_source.status()
    lnbits_balance = await get_total_balance()
    return BalanceDelta(
        lnbits_balance_msats=lnbits_balance,
        node_balance_msats=status.balance_msat,
    )
