from typing import NamedTuple

class Tournament(NamedTuple):
    id: str
    wallet: str
    tournament_name: str
    challonge_API: str
    challonge_tournament_id: str
    challonge_tournament_name: str
    signup_fee: int 
    prize_pool: int
    total_prize_pool: int
    max_participants: int
    current_participants: int
    status: str # STARTED, COMPLETED, COMPLETED_PAID, CANCELED
    winner_id: str
    webhook: str
    time: int # ??? timestamp
    start_time: int

class Participant(NamedTuple):
    id: str
    wallet: str
    tournament: str
    secret: str
    status: str # (SIGNUP, PAID)
    username: str
    challonge_username: str
