from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Tournament, Participant


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
        INSERT INTO participant (id, tournament, secret, status, username, challonge_username)
        VALUES (?, ?, ?, ?, ?, ?)
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
    if row[5] == "signup":
        await db.execute(
            """
            UPDATE participant
            SET status = paid
            WHERE id = ?
            """,
            (payment_hash,),
        )

        tournament = await get_tournament(row[1])
        assert tournament, "Couldn't get tournament from paid participant"

        current_participants = tournament.current_participants + 1
        total_prize_pool = tournament.prize_pool + tournament.signup_fee * current_participants
        await db.execute(
            """
            UPDATE participant
            SET 
                current_participants = ?,
                total_prize_pool = ?
            WHERE id = ?
            """,
            (current_participants, total_prize_pool, row[1]),
        )

    participant = await get_participant(payment_hash)
    return participant


async def get_participant(participant_id: str) -> Optional[Participant]:
    row = await db.fetchone(
        "SELECT s.*, FROM participant s WHERE s.id = ?",
        (participant_id,),
    )
    print(row)
    return Participant(**row) if row else None


async def get_participantByUsername(username: str) -> Optional[Participant]:
    row = await db.fetchone(
         "SELECT s.*, FROM participant s WHERE s.participant_name = ?",
        (username,),
    )
    print(row)
    return Participant(**row) if row else None


async def get_participants(wallet_ids: Union[str, List[str]]) -> List[Participant]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT s.*, FROM participant s WHERE s.wallet IN ({q})",
        (*wallet_ids,),
    )

    return [Participant(**row) for row in rows]


async def delete_participant(participant_id: str) -> None:
    await db.execute("DELETE FROM participant WHERE id = ?", (participant_id,))


# Tournaments


async def create_tournament(
    *,
    wallet: str,
    tournament_name: str,
    challonge_API: str,
    challonge_tournament_id: str,
    challonge_tournament_name: str,
    signup_fee: int,
    prize_pool: int,
    max_participants: int,
    webhook: str,
    start_time: int,
) -> Tournament:
    tournament_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO tournament (
            id,
            wallet,
            tournament_name,
            challonge_api,
            challonge_tournament_id,
            challonge_tournament_name,
            signup_fee,
            prize_pool,
            total_prize_pool,
            max_participants,
            current_participants,
            status,
            winner_id,
            webhook,
            time,
            start_time
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tournament_id, wallet, tournament_name, challonge_API, challonge_tournament_id, challonge_tournament_name,
         signup_fee, prize_pool, prize_pool, max_participants, 0, "STARTED", None , webhook, None, start_time ),
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
