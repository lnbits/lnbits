async def m001_initial(db):
    """
    Initial gertys table.
    """
    await db.execute(
        """
        CREATE TABLE gerty.gertys (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            wallet TEXT NOT NULL,
            lnbits_wallets TEXT,
            mempool_endpoint TEXT,
            exchange TEXT,
            show_lnbits_wallets_balance BOOL,
            show_sats_quote BOOL,
            show_pieter_wuille_facts BOOL,
            show_exchange_market_rate BOOL,
            show_onchain_difficulty_epoch_progress BOOL,
            show_onchain_difficulty_retarget_date BOOL,
            show_onchain_difficulty_blocks_remaining BOOL,
            show_onchain_difficulty_epoch_time_remaining BOOL,
            show_onchain_mempool_recommended_fees BOOL,
            show_onchain_mempool_number_of_tx BOOL,
            show_mining_current_hash_rate BOOL,
            show_mining_current_difficulty BOOL,
            show_lightning_channel_count BOOL,
            show_lightning_node_count BOOL,
            show_lightning_tor_node_count BOOL,
            show_lightning_clearnet_nodes BOOL,
            show_lightning_unannounced_nodes BOOL,
            show_lightning_average_channel_capacity BOOL
        );
    """
    )