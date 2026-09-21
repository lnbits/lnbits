# Onchain wallets

Choose **Onchain** in **Add wallet**, then select Mainnet, Testnet4 or Testnet3.
Each LNbits onchain wallet holds one Bitcoin wallet on one network.
The network badge appears in the wallet card header. Use **Set up wallet** to
configure it; to use another Bitcoin wallet, create another LNbits onchain wallet
from the sidebar. This limit is also enforced by the API and database.

The standard wallet card shows the Bitcoin wallet details and device connection
buttons beneath the wallet name, with a settings cog on the right. **Advanced** remains
expandable, followed by the usual wallet configuration and tools.

Add a server wallet, import a public descriptor/account key, or connect a supported
hardware wallet. Trezor and the existing serial hardware signing flows are
available. Watch-only accounts receive and track bitcoin; spending requires an
external signer. Server wallets sign on the LNbits server.

## Server wallets and recovery

The superuser enables server signing under **Settings → Payments → Onchain
payments**. Generate or restore the encryption key, download its backup, confirm
that it is stored safely, and enable payments. An environment key remains
supported through `LNBITS_ONCHAIN_MASTER_KEY`; UI-generated keys are stored in the
LNbits data directory and included in server backups.

Each server wallet also has its own recovery phrase. The Backup → Verify flow
checks words before enabling receive/send. Restoring a phrase derives native
SegWit account zero: `m/84'/0'/0'` on Mainnet or `m/84'/1'/0'` on the test networks,
without a BIP39 passphrase. Back up both the server encryption key/database and
individual wallet phrases. Disabling server signing does not disable phrase export.

## Balances, history and payments

The server scans both receive and change addresses. Confirmations, coins and
complete address histories persist in the core database. Refreshes run without an
open browser. During a scan, existing transactions remain visible and wallet
creation remains available. Failed requests preserve the previous snapshot and
show a stale-balance notice.

With the LNbits explorer selected, the wallet uses its existing block and address
WebSockets to request updates when activity arrives. Address subscriptions cover
the current receive address, recent receive addresses and funded addresses, up to
eight unique addresses. A one-minute state refresh covers all remaining addresses
and serves as the fallback for Mempool or disconnected sockets. Active scans are
checked every ten seconds. Hidden pages pause these requests, and charts refresh
only when confirmed activity changes after a scan finishes.

Sending uses a stable copy of the selected coins and change address while the
background view refreshes. Server signing checks that the selected coins remain
unspent. Review the recipients, change and fee before broadcasting. If a broadcast
request fails, check transaction status before submitting another payment.

Use **Wallet Config** for fiat currency tracking, wallet naming, icons and pinning.
The fiat equivalent and transaction fiat values use the current exchange rate.
Charts summarize this wallet's confirmed transactions; transaction history and
the main balance card show the same Bitcoin wallet.

Bitcoin balances are separate from Lightning balances. Lightning invoices,
LNURL/LndHub spending, virtual credit/debit and Lightning wallet sharing do not
operate on onchain wallets. Mobile browser access, core wallet keys and onchain
APIs are available from the standard wallet tools.

## Explorer and installation

Choose the provider using the settings cog beside the device buttons, then **Block explorer**. LNbits'
built-in block explorer is the default when enabled for the wallet's Bitcoin
network. Wallet operations reuse the shared service behind the block explorer API,
including history, coins, fees, signing inputs and broadcasts; its public API need
not be enabled. The administrator can select `test4` for a Testnet4 Electrum server.

Alternatively, select **Mempool**. The editable URL defaults to
`https://mempool.space`, with the appropriate test network selected automatically.
For another Mempool server, enter its full network-specific base URL, without
`/api` (for example `https://example.com/testnet4`). Localhost and LAN URLs are
supported for self-hosted Mempool instances. The selection is saved per LNbits wallet; transaction and
address links also open the selected explorer. No explorer environment variable
is required. Use a provider you trust with address history.

The native `wallycore` library is a standard LNbits dependency, installed by the
normal dependency installation or update process. No installation extra is needed
for onchain wallets.

## Existing Watchonly wallets

Watchonly remains a separate extension with its own data. Nothing is automatically
moved, deleted or re-encrypted. To follow an existing account in core, import its
public descriptor. To restore a server wallet, use its recovery phrase in core's
restore flow. Both interfaces then refer to the same Bitcoin funds; this does not
transfer or duplicate those funds.

## API access

Use the core wallet's `X-API-KEY`. Read keys can list accounts, retrieve persistent
state and obtain receive addresses. Admin keys also configure accounts, restore or
export phrases, sign and broadcast transactions. Keys are scoped to the LNbits
wallet, including when a user owns several wallets.

- `GET /onchain/api/v1/wallet`: list accounts.
- `GET /onchain/api/v1/state`: cached addresses, history, coins and scan status.
- `POST /onchain/api/v1/sync`: schedule a background update.
- `GET /onchain/api/v1/stats/daily`: confirmed transaction statistics.
- `POST /onchain/api/v1/hot-wallet`: create/restore a server wallet. Restoration
  uses `X-Onchain-Recovery-Phrase` so phrases do not enter request-body audit logs.

See the instance's `/docs#/Onchain` for the complete API schema.
