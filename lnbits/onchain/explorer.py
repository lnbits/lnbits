"""Wallet-scoped blockchain providers with a common Esplora-shaped result."""

import re

import httpx

from lnbits.core.services.blockexplorer import BlockExplorerWalletSession
from lnbits.settings import settings

from .models import Config

TXID = re.compile(r"^[0-9a-f]{64}$")
NETWORKS = {"main": "Mainnet", "test": "Testnet", "test4": "Testnet4"}


def local_explorer_network() -> str | None:
    if not settings.lnbits_blockexplorer_enabled:
        return None
    return NETWORKS.get(settings.lnbits_blockexplorer_network)


def provider_name(config: Config) -> str:
    if config.explorer_provider == "auto":
        return "lnbits" if local_explorer_network() == config.network else "mempool"
    return config.explorer_provider


def mempool_url(config: Config) -> str:
    endpoint = config.mempool_endpoint.rstrip("/")
    # The standard host serves multiple chains; custom URLs identify one chain.
    if endpoint == "https://mempool.space":
        endpoint += {"Mainnet": "", "Testnet": "/testnet", "Testnet4": "/testnet4"}[
            config.network
        ]
    return endpoint


def explorer_url(config: Config) -> str:
    return (
        "/blockexplorer" if provider_name(config) == "lnbits" else mempool_url(config)
    )


class MempoolExplorer:
    def __init__(self, config: Config, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(
            base_url=mempool_url(config) + "/",
            timeout=15,
            follow_redirects=False,
            trust_env=False,
        )

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.client.__aexit__(*args)

    async def history(self, address: str) -> list[dict]:
        response = await self.client.get(f"api/address/{address}/txs")
        response.raise_for_status()
        transactions = response.json()
        seen: set[str] = set()
        for _ in range(1000):
            if not isinstance(transactions, list):
                raise ValueError("Invalid explorer response")
            confirmed = [tx for tx in transactions if tx["status"]["confirmed"]]
            if not confirmed or len(confirmed) % 25:
                break
            last = confirmed[-1]["txid"]
            if last in seen or not TXID.fullmatch(last):
                raise ValueError("Invalid explorer pagination")
            seen.add(last)
            response = await self.client.get(f"api/address/{address}/txs/chain/{last}")
            response.raise_for_status()
            page = response.json()
            if not isinstance(page, list):
                raise ValueError("Invalid explorer response")
            transactions.extend(page)
            if len(page) < 25:
                break
        else:
            raise ValueError("Explorer history limit reached")
        result = {}
        for tx in transactions:
            if not TXID.fullmatch(tx["txid"]):
                raise ValueError("Invalid transaction ID")
            result[tx["txid"]] = tx
        return list(result.values())

    async def utxos(self, address: str) -> list[dict]:
        response = await self.client.get(f"api/address/{address}/utxo")
        response.raise_for_status()
        return response.json()

    async def fees(self) -> dict:
        response = await self.client.get("api/v1/fees/recommended")
        response.raise_for_status()
        return response.json()

    async def raw_transaction(self, txid: str) -> str:
        response = await self.client.get(f"api/tx/{txid}/hex")
        response.raise_for_status()
        return response.text.strip()

    async def broadcast(self, raw: str) -> str:
        response = await self.client.post("api/tx", content=raw)
        response.raise_for_status()
        return response.text.strip()


class LnbitsExplorer(BlockExplorerWalletSession):
    def __init__(self, config: Config):
        if local_explorer_network() != config.network:
            raise ValueError("LNbits block explorer is unavailable for this network")
        super().__init__()


Explorer = MempoolExplorer | LnbitsExplorer


def explorer_client(config: Config) -> Explorer:
    if provider_name(config) == "lnbits":
        return LnbitsExplorer(config)
    return MempoolExplorer(config)
