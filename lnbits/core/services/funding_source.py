from loguru import logger

from lnbits.core.models.notifications import NotificationType
from lnbits.core.services.notifications import enqueue_notification
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
        lnbits_balance_sats=int(lnbits_balance) // 1000,
        node_balance_sats=status.balance_msat // 1000,
    )


async def check_server_balance_against_node():
    """
    Watchdog will check lnbits balance and nodebalance
    and will switch to VoidWallet if the watchdog delta is reached.
    """
    if (
        not settings.lnbits_watchdog_switch_to_voidwallet
        and not settings.lnbits_notification_watchdog
    ):
        return

    funding_source = get_funding_source()
    if funding_source.__class__.__name__ == "VoidWallet":
        return

    status = await get_balance_delta()
    if status.delta_sats < settings.lnbits_watchdog_delta:
        return

    use_voidwallet = settings.lnbits_watchdog_switch_to_voidwallet
    logger.warning(
        f"Balance delta reached: {status.delta_sats} sats."
        f" Switch to void wallet: {use_voidwallet}."
    )
    enqueue_notification(
        NotificationType.watchdog_check,
        {
            "delta_sats": status.delta_sats,
            "lnbits_balance_sats": status.lnbits_balance_sats,
            "node_balance_sats": status.node_balance_sats,
            "switch_to_void_wallet": use_voidwallet,
        },
    )
    if use_voidwallet:
        logger.error(f"Switching to VoidWallet. Delta: {status.delta_sats} sats.")
        await switch_to_voidwallet()


async def check_balance_delta_changed():
    status = await get_balance_delta()
    if settings.latest_balance_delta_sats is None:
        settings.latest_balance_delta_sats = status.delta_sats
        return
    if status.delta_sats != settings.latest_balance_delta_sats:
        enqueue_notification(
            NotificationType.balance_delta,
            {
                "delta_sats": status.delta_sats,
                "old_delta_sats": settings.latest_balance_delta_sats,
                "lnbits_balance_sats": status.lnbits_balance_sats,
                "node_balance_sats": status.node_balance_sats,
            },
        )
    settings.latest_balance_delta_sats = status.delta_sats
