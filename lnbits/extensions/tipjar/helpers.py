from lnbits.core.crud import get_wallet
from .crud import get_tipjar


async def get_charge_details(tipjar_id):
    """Return the default details for a satspay charge"""
    details = {
        "time": 1440,
    }
    tipjar = await get_tipjar(tipjar_id)
    wallet_id = tipjar.wallet
    wallet = await get_wallet(wallet_id)
    user = wallet.user
    details["user"] = user
    details["lnbitswallet"] = wallet_id
    details["onchainwallet"] = tipjar.onchain
    return details
