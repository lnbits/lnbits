from typing import List, Optional

from . import db
from .models import Wallets, Addresses, Mempool

from lnbits.helpers import urlsafe_short_hash

from embit.descriptor import Descriptor, Key  # type: ignore
from embit.descriptor.arguments import AllowedDerivation  # type: ignore
from embit.networks import NETWORKS  # type: ignore


##########################WALLETS####################


def detect_network(k):
    version = k.key.version
    for network_name in NETWORKS:
        net = NETWORKS[network_name]
        # not found in this network
        if version in [net["xpub"], net["ypub"], net["zpub"], net["Zpub"], net["Ypub"]]:
            return net


def parse_key(masterpub: str):
    """Parses masterpub or descriptor and returns a tuple: (Descriptor, network)
    To create addresses use descriptor.derive(num).address(network=network)
    """
    network = None
    # probably a single key
    if "(" not in masterpub:
        k = Key.from_string(masterpub)
        if not k.is_extended:
            raise ValueError("The key is not a master public key")
        if k.is_private:
            raise ValueError("Private keys are not allowed")
        # check depth
        if k.key.depth != 3:
            raise ValueError(
                "Non-standard depth. Only bip44, bip49 and bip84 are supported with bare xpubs. For custom derivation paths use descriptors."
            )
        # if allowed derivation is not provided use default /{0,1}/*
        if k.allowed_derivation is None:
            k.allowed_derivation = AllowedDerivation.default()
        # get version bytes
        version = k.key.version
        for network_name in NETWORKS:
            net = NETWORKS[network_name]
            # not found in this network
            if version in [net["xpub"], net["ypub"], net["zpub"]]:
                network = net
                if version == net["xpub"]:
                    desc = Descriptor.from_string("pkh(%s)" % str(k))
                elif version == net["ypub"]:
                    desc = Descriptor.from_string("sh(wpkh(%s))" % str(k))
                elif version == net["zpub"]:
                    desc = Descriptor.from_string("wpkh(%s)" % str(k))
                break
        # we didn't find correct version
        if network is None:
            raise ValueError("Unknown master public key version")
    else:
        desc = Descriptor.from_string(masterpub)
        if not desc.is_wildcard:
            raise ValueError("Descriptor should have wildcards")
        for k in desc.keys:
            if k.is_extended:
                net = detect_network(k)
                if net is None:
                    raise ValueError(f"Unknown version: {k}")
                if network is not None and network != net:
                    raise ValueError("Keys from different networks")
                network = net
    return desc, network


async def create_watch_wallet(*, user: str, masterpub: str, title: str) -> Wallets:
    # check the masterpub is fine, it will raise an exception if not
    parse_key(masterpub)
    wallet_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO watchonly.wallets (
            id,
            "user",
            masterpub,
            title,
            address_no,
            balance
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        # address_no is -1 so fresh address on empty wallet can get address with index 0
        (wallet_id, user, masterpub, title, -1, 0),
    )

    return await get_watch_wallet(wallet_id)


async def get_watch_wallet(wallet_id: str) -> Optional[Wallets]:
    row = await db.fetchone(
        "SELECT * FROM watchonly.wallets WHERE id = ?", (wallet_id,)
    )
    return Wallets.from_row(row) if row else None


async def get_watch_wallets(user: str) -> List[Wallets]:
    rows = await db.fetchall(
        """SELECT * FROM watchonly.wallets WHERE "user" = ?""", (user,)
    )
    return [Wallets(**row) for row in rows]


async def update_watch_wallet(wallet_id: str, **kwargs) -> Optional[Wallets]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    await db.execute(
        f"UPDATE watchonly.wallets SET {q} WHERE id = ?", (*kwargs.values(), wallet_id)
    )
    row = await db.fetchone(
        "SELECT * FROM watchonly.wallets WHERE id = ?", (wallet_id,)
    )
    return Wallets.from_row(row) if row else None


async def delete_watch_wallet(wallet_id: str) -> None:
    await db.execute("DELETE FROM watchonly.wallets WHERE id = ?", (wallet_id,))

    ########################ADDRESSES#######################


async def get_derive_address(wallet_id: str, num: int):
    wallet = await get_watch_wallet(wallet_id)
    key = wallet[2]
    desc, network = parse_key(key)
    return desc.derive(num).address(network=network)


async def get_fresh_address(wallet_id: str) -> Optional[Addresses]:
    wallet = await get_watch_wallet(wallet_id)
    if not wallet:
        return None

    address = await get_derive_address(wallet_id, wallet[4] + 1)

    await update_watch_wallet(wallet_id=wallet_id, address_no=wallet[4] + 1)
    masterpub_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO watchonly.addresses (
            id,
            address,
            wallet,
            amount
        )
        VALUES (?, ?, ?, ?)
        """,
        (masterpub_id, address, wallet_id, 0),
    )

    return await get_address(address)


async def get_address(address: str) -> Optional[Addresses]:
    row = await db.fetchone(
        "SELECT * FROM watchonly.addresses WHERE address = ?", (address,)
    )
    return Addresses.from_row(row) if row else None


async def get_addresses(wallet_id: str) -> List[Addresses]:
    rows = await db.fetchall(
        "SELECT * FROM watchonly.addresses WHERE wallet = ?", (wallet_id,)
    )
    return [Addresses(**row) for row in rows]


######################MEMPOOL#######################


async def create_mempool(user: str) -> Optional[Mempool]:
    await db.execute(
        """
        INSERT INTO watchonly.mempool ("user",endpoint) 
        VALUES (?, ?)
        """,
        (user, "https://mempool.space"),
    )
    row = await db.fetchone(
        """SELECT * FROM watchonly.mempool WHERE "user" = ?""", (user,)
    )
    return Mempool.from_row(row) if row else None


async def update_mempool(user: str, **kwargs) -> Optional[Mempool]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    await db.execute(
        f"""UPDATE watchonly.mempool SET {q} WHERE "user" = ?""",
        (*kwargs.values(), user),
    )
    row = await db.fetchone(
        """SELECT * FROM watchonly.mempool WHERE "user" = ?""", (user,)
    )
    return Mempool.from_row(row) if row else None


async def get_mempool(user: str) -> Mempool:
    row = await db.fetchone(
        """SELECT * FROM watchonly.mempool WHERE "user" = ?""", (user,)
    )
    return Mempool.from_row(row) if row else None
