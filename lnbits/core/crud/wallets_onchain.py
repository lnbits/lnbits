from sqlalchemy import text  # type: ignore[import-untyped]

from lnbits.core.db import db
from lnbits.core.models.wallets import OnchainConfig, OnchainWallet


class WalletAlreadyConfiguredError(ValueError):
    def __init__(self):
        super().__init__(
            "This LNbits wallet is already configured. "
            "Create another LNbits onchain wallet to set up another Bitcoin wallet."
        )


async def init_onchain_wallet(
    wallet: OnchainWallet, encrypted_seed: str | None = None
) -> OnchainWallet:
    meta = wallet.onchain_meta.copy()
    meta.sync_checked_at = 0
    meta.sync_error = None
    # One conditional write stores setup and recovery material together and
    # protects against competing setup requests.
    result = await db.execute(
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
        if await get_onchain_wallet(wallet.id):
            raise WalletAlreadyConfiguredError()
        raise ValueError("Onchain wallet is unavailable for setup")
    configured = await get_onchain_wallet(wallet.id)
    assert configured
    return configured


async def get_onchain_wallet(
    wallet_id: str, *, include_unconfigured: bool = False
) -> OnchainWallet | None:
    return await db.fetchone(
        """
        SELECT *, COALESCE((SELECT balance FROM balances
            WHERE wallet_id = wallets.id), 0) AS balance_msat
        FROM wallets WHERE id = :id AND wallet_type = 'onchain'
            AND (:include_unconfigured = true OR onchain_wallet_kind IS NOT NULL)
        """,
        {"id": wallet_id, "include_unconfigured": include_unconfigured},
        OnchainWallet,
    )


async def get_onchain_wallets(
    wallet_id: str, network: str | None = None
) -> list[OnchainWallet]:
    wallet = await get_onchain_wallet(wallet_id)
    return (
        [wallet]
        if wallet and (not network or wallet.onchain_network == network)
        else []
    )


async def update_onchain_wallet(wallet: OnchainWallet) -> OnchainWallet:
    # Backup confirmation must not rewrite descriptor, seed, or scanner metadata.
    await db.execute(
        """UPDATE wallets SET onchain_backup_confirmed = :confirmed
        WHERE id = :id AND wallet_type = 'onchain' AND onchain_wallet_kind = 'hot'""",
        {"id": wallet.id, "confirmed": wallet.onchain_backup_confirmed},
    )
    updated = await get_onchain_wallet(wallet.id)
    assert updated
    return updated


async def clear_onchain_wallet_data(wallet_id: str) -> None:
    async with db.connect() as conn:
        async with conn.conn.begin():
            result = await conn.conn.execute(
                text("""
                    UPDATE wallets SET onchain_meta = '{}', onchain_config = '{}',
                        onchain_network = NULL, onchain_wallet_kind = NULL,
                        onchain_address_no = -1, onchain_backup_confirmed = false,
                        onchain_sync_lease_until = 0
                    WHERE id = :id AND wallet_type = 'onchain'
                        AND onchain_wallet_kind = 'watch'
                        AND onchain_encrypted_seed IS NULL
                """),
                {"id": wallet_id},
            )
            if result.rowcount != 1:
                raise ValueError("Onchain wallet cannot be removed")
            await conn.conn.execute(
                text("DELETE FROM onchain_addresses WHERE wallet = :id"),
                {"id": wallet_id},
            )


async def update_config(
    config: OnchainConfig, wallet_id: str, network: str | None = None
) -> OnchainConfig:
    result = await db.execute(
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
    if result.rowcount != 1:
        raise ValueError(
            "Create another LNbits wallet to use a different Bitcoin network"
        )
    return config
