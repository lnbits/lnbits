from lnbits.core.db import db
from lnbits.core.models.wallets import OnchainConfig, OnchainWallet
from lnbits.db import Connection


class WalletAlreadyConfiguredError(ValueError):
    def __init__(self):
        super().__init__(
            "This LNbits wallet is already configured. "
            "Create another LNbits onchain wallet to set up another Bitcoin wallet."
        )


async def init_onchain_wallet(
    wallet: OnchainWallet,
    encrypted_seed: str | None = None,
    conn: Connection | None = None,
) -> OnchainWallet:
    meta = wallet.onchain_meta.copy()
    meta.sync_checked_at = 0
    meta.sync_error = None
    # One conditional write stores setup and recovery material together and
    # protects against competing setup requests.
    result = await (conn or db).execute(
        """UPDATE wallets SET name = :title, onchain_meta = :meta,
            onchain_network = :network, onchain_wallet_kind = :kind,
            onchain_address_no = -1, onchain_backup_confirmed = false,
            onchain_encrypted_seed = :seed, onchain_sync_lease_until = 0
        WHERE id = :id AND wallet_type = 'onchain' AND deleted = false
            AND onchain_wallet_kind IS NULL""",
        {
            "id": wallet.id,
            "title": wallet.name,
            "meta": meta.json(by_alias=True),
            "network": wallet.onchain_network,
            "kind": wallet.onchain_wallet_kind,
            "seed": encrypted_seed,
        },
    )
    if result.rowcount != 1:
        existing = await get_onchain_wallet(wallet.id, conn=conn)
        if existing and existing.onchain_wallet_kind:
            raise WalletAlreadyConfiguredError()
        raise ValueError("Onchain wallet is unavailable for setup")
    configured = await get_onchain_wallet(wallet.id, conn=conn)
    assert configured
    return configured


async def get_onchain_wallet(
    wallet_id: str, deleted: bool | None = False, conn: Connection | None = None
) -> OnchainWallet | None:
    query = """
        SELECT *, COALESCE((SELECT balance FROM balances
            WHERE wallet_id = wallets.id), 0) AS balance_msat
        FROM wallets WHERE id = :id AND wallet_type = 'onchain'
        """
    if deleted is not None:
        query += " AND deleted = :deleted "
    return await (conn or db).fetchone(
        query,
        {"id": wallet_id, "deleted": deleted},
        OnchainWallet,
    )


async def update_onchain_wallet(
    wallet: OnchainWallet, conn: Connection | None = None
) -> OnchainWallet:
    # Backup confirmation must not rewrite descriptor, seed, or scanner metadata.
    await (conn or db).execute(
        """UPDATE wallets SET onchain_backup_confirmed = :confirmed
        WHERE id = :id AND wallet_type = 'onchain' AND onchain_wallet_kind = 'hot'""",
        {"id": wallet.id, "confirmed": wallet.onchain_backup_confirmed},
    )
    updated = await get_onchain_wallet(wallet.id, conn=conn)
    assert updated
    return updated


async def clear_onchain_wallet_data(
    wallet_id: str, conn: Connection | None = None
) -> None:
    result = await (conn or db).execute(
        """
        UPDATE wallets SET onchain_meta = '{}', onchain_config = '{}',
            onchain_network = NULL, onchain_wallet_kind = NULL,
            onchain_address_no = -1, onchain_backup_confirmed = false,
            onchain_sync_lease_until = 0
        WHERE id = :id AND wallet_type = 'onchain'
            AND onchain_wallet_kind = 'watch'
            AND onchain_encrypted_seed IS NULL
        """,
        {"id": wallet_id},
    )
    if result.rowcount != 1:
        raise ValueError("Onchain wallet cannot be removed")
    await (conn or db).execute(
        "DELETE FROM onchain_addresses WHERE wallet = :id",
        {"id": wallet_id},
    )


async def update_onchain_wallet_config(
    config: OnchainConfig,
    wallet_id: str,
    network: str | None = None,
    conn: Connection | None = None,
) -> None:
    await (conn or db).execute(
        """UPDATE wallets SET onchain_config = :config,
            onchain_network = COALESCE(:network, onchain_network, 'Mainnet')
        WHERE id = :id AND wallet_type = 'onchain'
            AND (onchain_wallet_kind IS NULL OR :network IS NULL
                OR onchain_network = :network)""",
        {
            "id": wallet_id,
            "config": config.json(exclude={"network"}),
            "network": network,
        },
    )
