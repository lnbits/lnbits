from lnbits.wallets.base import Wallet
from typing import NamedTuple

class Tournament(NamedTuple):
    id: str
    wallet: str
    challonge_api: str
    challonge_tournament_id: str
    signup_fee: int 
    winner_id: str
    webhook: str
    time: str
    
class Participant(NamedTuple):
    id: str
    wallet: str
    tournament: str
    secret: str
    status: str # (SIGNUP, PAID)
    username: str
    challonge_username: str
