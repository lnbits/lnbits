"""Configure the isolated regtest provider after its migrations have run."""

import asyncio
from pathlib import Path
from urllib.parse import quote

from coincurve import PrivateKey
from lnbits.extensions.nwcprovider.crud import (
    create_nwc,
    get_config_nwc,
    get_nwc,
    set_config_nwc,
)
from lnbits.extensions.nwcprovider.models import CreateNWCKey, GetNWC

from lnbits.core.crud import get_user
from lnbits.core.models import Account
from lnbits.core.services import create_user_account, update_wallet_balance

# Public test credentials, valid only for this local regtest fixture.
USER_ID = "bbbbbbbbbbbb4bbb8bbbbbbbbbbbbbbb"
CLIENT_SECRET = "11" * 32


async def main():
    user = await get_user(USER_ID)
    if not user:
        user = await create_user_account(Account(id=USER_ID), wallet_name="NWC regtest")
    if not user.wallets:
        raise RuntimeError("NWC regtest account has no wallet.")
    wallet = user.wallets[0]
    if wallet.balance < 1_000_000:
        await update_wallet_balance(
            wallet, 1_000_000 - wallet.balance, "NWC regtest balance"
        )

    client_pubkey = (
        PrivateKey(bytes.fromhex(CLIENT_SECRET)).public_key_xonly.format().hex()
    )
    if not await get_nwc(GetNWC(pubkey=client_pubkey)):
        await create_nwc(
            CreateNWCKey(
                pubkey=client_pubkey,
                wallet=wallet.id,
                description="NWC regtest funding source",
                expires_at=0,
                permissions=["pay", "invoice", "lookup", "history", "balance", "info"],
                budgets=[],
            )
        )
    await set_config_nwc("relay", "ws://nwc-relay:7777")
    await set_config_nwc("relay_alias", "ws://127.0.0.1:7777")
    provider_secret = await get_config_nwc("provider_key")
    if not provider_secret:
        raise RuntimeError("NWC provider key was not initialized.")
    provider_pubkey = (
        PrivateKey(bytes.fromhex(provider_secret)).public_key_xonly.format().hex()
    )
    relay = quote("ws://127.0.0.1:7777", safe="")
    pairing_url = (
        f"nostr+walletconnect://{provider_pubkey}?relay={relay}&secret={CLIENT_SECRET}"
    )
    Path("data/nwc.env").write_text(
        f"export LNBITS_BACKEND_WALLET_CLASS=NWCWallet\n"
        f"export LNBITS_FUNDING_SOURCE_PAY_INVOICE_WAIT_SECONDS=60\n"
        f"export NWC_PAIRING_URL='{pairing_url}'\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
