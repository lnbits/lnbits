from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Tournament, Participant
from lnbits.extensions import challonge


async def create_participant(
    payment_hash: str,
    wallet: str,
    tournament: str,
    secret: str,
    status: str, # signup / paid / winner
    username: str,
    challonge_username: str
) -> Participant:
    await db.execute(
        """
        INSERT INTO participant (id, wallet, tournament, secret, status, username, challonge_username)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (payment_hash, wallet, tournament, secret, status, username, challonge_username),
    )

    participant = await get_participant(payment_hash)
    assert participant, "Newly created subdomain couldn't be retrieved"
    return participant


async def set_participant_paid(payment_hash: str) -> Participant:
    row = await db.fetchone(
        "SELECT p.* FROM participant p WHERE p.id = ?",
        (payment_hash,),
    )
    if row['status'] == "signup":
        await db.execute(
            """
            UPDATE participant
            SET status = "paid"
            WHERE id = ?
            """,
            (payment_hash,),
        )

    participant = await get_participant(payment_hash)
    return participant


async def get_participant(participant_id: str) -> Optional[Participant]:
    row = await db.fetchone(
        "SELECT s.* FROM participant s WHERE s.id = ?",
        (participant_id,),
    )
    print(row)
    return Participant(**row) if row else None


async def get_participantByUsername(challonge_username: str, username: str) -> Optional[Participant]:
    row = await db.fetchone(
         "SELECT s.* FROM participant s WHERE s.challonge_username = ? and s.username = ?",
        (challonge_username, username),
    )
    print(row)
    return Participant(**row) if row else None


async def get_participants(wallet_ids: Union[str, List[str]]) -> List[Participant]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT s.* FROM participant s WHERE s.wallet IN ({q})",
        (*wallet_ids,),
    )

    return [Participant(**row) for row in rows]


async def delete_participant(participant_id: str) -> None:
    await db.execute("DELETE FROM participant WHERE id = ?", (participant_id,))


# Tournaments


async def create_tournament(
    *,
    wallet: str,
    challonge_API: str,
    challonge_tournament_id: str,
    signup_fee: int,
    webhook: str
) -> Tournament:
    tournament_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO tournament (
            id,
            wallet,
            challonge_api,
            challonge_tournament_id,
            signup_fee,
            winner_id,
            webhook
            )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (tournament_id, wallet, challonge_API, challonge_tournament_id, signup_fee, None , webhook ),
    )

    tournament = await get_tournament(tournament_id)
    assert tournament, "Newly created domain couldn't be retrieved"
    return tournament


async def update_tournament(tournament_id: str, **kwargs) -> Tournament:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(f"UPDATE tournament SET {q} WHERE id = ?", (*kwargs.values(), tournament_id))
    row = await db.fetchone("SELECT * FROM tournament WHERE id = ?", (tournament_id,))
    assert row, "Newly updated tournament couldn't be retrieved"
    return Tournament(**row)


async def get_tournament(tournament_id: str) -> Optional[Tournament]:
    row = await db.fetchone("SELECT * FROM tournament WHERE id = ?", (tournament_id,))
    return Tournament(**row) if row else None


async def get_tournaments(wallet_ids: Union[str, List[str]]) -> List[Tournament]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(f"SELECT * FROM tournament WHERE wallet IN ({q})", (*wallet_ids,))

    return [Tournament(**row) for row in rows]


async def delete_tournament(domain_id: str) -> None:
    await db.execute("DELETE FROM tournament WHERE id = ?", (domain_id,))
