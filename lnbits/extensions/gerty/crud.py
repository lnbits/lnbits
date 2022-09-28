from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Gerty


async def create_gerty(wallet_id: str, data: Gerty) -> Gerty:
    gerty_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO gerty.gertys (
        id,
        name,
        wallet,
        lnbits_wallets,
        mempool_endpoint,
        exchange,
        show_lnbits_wallets_balance,
        show_sats_quote,
        show_pieter_wuille_facts,
        show_exchange_market_rate,
        show_onchain_difficulty_epoch_progress,
        show_onchain_difficulty_retarget_date,
        show_onchain_difficulty_blocks_remaining,
        show_onchain_difficulty_epoch_time_remaining,
        show_onchain_mempool_recommended_fees,
        show_onchain_mempool_number_of_tx,
        show_mining_current_hash_rate,
        show_mining_current_difficulty,
        show_lightning_channel_count,
        show_lightning_node_count,
        show_lightning_tor_node_count,
        show_lightning_clearnet_nodes,
        show_lightning_unannounced_nodes,
        show_lightning_average_channel_capacity
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gerty_id,
            data.name,
            data.wallet,
            data.lnbits_wallets,
            data.mempool_endpoint,
            data.exchange,
            data.show_lnbits_wallets_balance,
            data.show_sats_quote,
            data.show_pieter_wuille_facts,
            data.show_exchange_market_rate,
            data.show_onchain_difficulty_epoch_progress,
            data.show_onchain_difficulty_retarget_date,
            data.show_onchain_difficulty_blocks_remaining,
            data.show_onchain_difficulty_epoch_time_remaining,
            data.show_onchain_mempool_recommended_fees,
            data.show_onchain_mempool_number_of_tx,
            data.show_mining_current_hash_rate,
            data.show_mining_current_difficulty,
            data.show_lightning_channel_count,
            data.show_lightning_node_count,
            data.show_lightning_tor_node_count,
            data.show_lightning_clearnet_nodes,
            data.show_lightning_unannounced_nodes,
            data.show_lightning_average_channel_capacity
        ),
    )

    gerty = await get_gerty(gerty_id)
    assert gerty, "Newly created gerty couldn't be retrieved"
    return gerty

async def update_gerty(gerty_id: str, **kwargs) -> Gerty:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE gerty.gertys SET {q} WHERE id = ?", (*kwargs.values(), gerty_id)
    )
    return await get_gerty(gerty_id)

async def get_gerty(gerty_id: str) -> Optional[Gerty]:
    row = await db.fetchone("SELECT * FROM gerty.gertys WHERE id = ?", (gerty_id,))
    return Gerty(**row) if row else None


async def get_gertys(wallet_ids: Union[str, List[str]]) -> List[Gerty]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM gerty.gertys WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Gerty(**row) for row in rows]


async def delete_gerty(gerty_id: str) -> None:
    await db.execute("DELETE FROM gerty.gertys WHERE id = ?", (gerty_id,))
