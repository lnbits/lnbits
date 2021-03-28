from typing import NamedTuple

class TournamentDTO(NamedTuple):
    id: str
    wallet: str
    challonge_tournament_id: str
    signup_fee: int 
    winner_id: str
    webhook: str
    name: str
    description: str
    started_at: str
    completed_at: str
    state: str
    signup_cap: str
    participants_count: int

class ParticipantDTO(NamedTuple):
    id: str
    wallet: str
    tournament: str
    secret: str
    status: str # (SIGNUP, PAID)
    username: str
    challonge_username: str
    email: str
