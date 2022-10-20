from typing import List, Optional, Union

from . import db
from .models import Cashu


async def create_cashu(
    cashu_id: str, keyset_id: str, wallet_id: str, data: Cashu
) -> Cashu:

    await db.execute(
        """
        INSERT INTO cashu.cashu (id, wallet, name, tickershort, fraction, maxsats, coins, keyset_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cashu_id,
            wallet_id,
            data.name,
            data.tickershort,
            data.fraction,
            data.maxsats,
            data.coins,
            keyset_id,
        ),
    )

    cashu = await get_cashu(cashu_id)
    assert cashu, "Newly created cashu couldn't be retrieved"
    return cashu


# async def update_cashu_keys(cashu_id, wif: str = None) -> Optional[Cashu]:
#     entropy = bytes([random.getrandbits(8) for i in range(16)])
#     mnemonic = bip39.mnemonic_from_bytes(entropy)
#     seed = bip39.mnemonic_to_seed(mnemonic)
#     root = bip32.HDKey.from_seed(seed, version=NETWORKS["main"]["xprv"])

#     bip44_xprv = root.derive("m/44h/1h/0h")
#     bip44_xpub = bip44_xprv.to_public()

#     await db.execute(
#         "UPDATE cashu.cashu SET prv = ?, pub = ? WHERE id = ?",
#         bip44_xprv.to_base58(),
#         bip44_xpub.to_base58(),
#         cashu_id,
#     )
#     row = await db.fetchone("SELECT * FROM cashu.cashu WHERE id = ?", (cashu_id,))
#     return Cashu(**row) if row else None


async def get_cashu(cashu_id) -> Optional[Cashu]:
    row = await db.fetchone("SELECT * FROM cashu.cashu WHERE id = ?", (cashu_id,))
    return Cashu(**row) if row else None


async def get_cashus(wallet_ids: Union[str, List[str]]) -> List[Cashu]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM cashu.cashu WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Cashu(**row) for row in rows]


async def delete_cashu(cashu_id) -> None:
    await db.execute("DELETE FROM cashu.cashu WHERE id = ?", (cashu_id,))


# ##########################################
# ###############MINT STUFF#################
# ##########################################


# async def store_promises(
#     amounts: List[int], B_s: List[str], C_s: List[str], cashu_id: str
# ):
#     for amount, B_, C_ in zip(amounts, B_s, C_s):
#         await store_promise(amount, B_, C_, cashu_id)


# async def get_promises(cashu_id) -> Optional[Cashu]:
#     row = await db.fetchall(
#         "SELECT * FROM cashu.promises WHERE cashu_id = ?", (cashu_id,)
#     )
#     return Promises(**row) if row else None


# ########################################
# ############ MINT INVOICES #############
# ########################################


##############################
######### KEYSETS ############
##############################
