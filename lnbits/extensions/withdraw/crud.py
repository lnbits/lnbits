from datetime import datetime
from typing import List, Optional, Union
import shortuuid # type: ignore
from lnbits.db import open_ext_db
from lnbits.helpers import urlsafe_short_hash

from .models import WithdrawLink


def create_withdraw_link(
    *,
    wallet_id: str,
    title: str,
    min_withdrawable: int,
    max_withdrawable: int,
    uses: int,
    wait_time: int,
    is_unique: bool,
    usescsv: str,
) -> WithdrawLink:

    with open_ext_db("withdraw") as db:

        link_id = urlsafe_short_hash()
        db.execute(
            """
            INSERT INTO withdraw_link (
                id,
                wallet,
                title,
                min_withdrawable,
                max_withdrawable,
                uses,
                wait_time,
                is_unique,
                unique_hash,
                k1,
                open_time,
                usescsv
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link_id,
                wallet_id,
                title,
                min_withdrawable,
                max_withdrawable,
                uses,
                wait_time,
                int(is_unique),
                urlsafe_short_hash(),
                urlsafe_short_hash(),
                int(datetime.now().timestamp()) + wait_time,
                usescsv,
            ),
        )
    return get_withdraw_link(link_id, uses)


def get_withdraw_link(link_id: str, num=None) -> Optional[WithdrawLink]:
    with open_ext_db("withdraw") as db:
        row = db.fetchone("SELECT * FROM withdraw_link WHERE id = ?", (link_id,))
        link = []
        for item in row:
           link.append(item) 
    tohash = row["id"] + row["unique_hash"] + str(num)
    link.append(shortuuid.uuid(name=tohash))
    return WithdrawLink._make(link)


def get_withdraw_link_by_hash(unique_hash: str, num=None) -> Optional[WithdrawLink]:
    with open_ext_db("withdraw") as db:
        row = db.fetchone("SELECT * FROM withdraw_link WHERE unique_hash = ?", (unique_hash,))
        link = []
        for item in row:
           link.append(item) 
        if not num:
            link.append("")
            return WithdrawLink._make(link)
    tohash = row["id"] + row["unique_hash"] + str(num)
    link.append(shortuuid.uuid(name=tohash))
    return WithdrawLink._make(link)
    


def get_withdraw_links(wallet_ids: Union[str, List[str]]) -> List[WithdrawLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("withdraw") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM withdraw_link WHERE wallet IN ({q})", (*wallet_ids,))

    return [WithdrawLink.from_row(row) for row in rows]


def update_withdraw_link(link_id: str, **kwargs) -> Optional[WithdrawLink]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    with open_ext_db("withdraw") as db:
        db.execute(f"UPDATE withdraw_link SET {q} WHERE id = ?", (*kwargs.values(), link_id))
        row = db.fetchone("SELECT * FROM withdraw_link WHERE id = ?", (link_id,))

    return WithdrawLink.from_row(row) if row else None


def delete_withdraw_link(link_id: str) -> None:
    with open_ext_db("withdraw") as db:
        db.execute("DELETE FROM withdraw_link WHERE id = ?", (link_id,))

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]