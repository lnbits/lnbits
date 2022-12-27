import calendar
import datetime

from boltz_client.boltz import BoltzClient, BoltzConfig

from lnbits.core.services import fee_reserve, get_wallet
from lnbits.settings import settings


def create_boltz_client() -> BoltzClient:
    config = BoltzConfig(
        network=settings.boltz_network,
        api_url=settings.boltz_url,
        mempool_url=f"{settings.boltz_mempool_space_url}/api",
        mempool_ws_url=f"{settings.boltz_mempool_space_url_ws}/api/v1/ws",
        referral_id="lnbits",
    )
    return BoltzClient(config)


async def check_balance(data) -> bool:
    # check if we can pay the invoice before we create the actual swap on boltz
    amount_msat = data.amount * 1000
    fee_reserve_msat = fee_reserve(amount_msat)
    wallet = await get_wallet(data.wallet)
    assert wallet
    if wallet.balance_msat - fee_reserve_msat < amount_msat:
        return False
    return True


def get_timestamp():
    date = datetime.datetime.utcnow()
    return calendar.timegm(date.utctimetuple())
