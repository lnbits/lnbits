from lnbits.core.crud import get_wallet
from .crud import get_tipjar


async def get_charge_details(tipjar_id):
    """Return the default details for a satspay charge"""
    tipjar = await get_tipjar(tipjar_id)
    wallet_id = tipjar.wallet
    wallet = await get_wallet(wallet_id)
    user = wallet.user
    details = {
        "time": 1440,
        "user": user,
        "lnbitswallet": wallet_id,
        "onchainwallet": tipjar.onchain,
        "completelink": "/tipjar/" + str(tipjar_id),
        "completelinktext": "Thanks for the tip!"
    }
    return details
