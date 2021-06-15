from typing import NamedTuple, Optional

class Royalty(NamedTuple):
    id:str
    paid:bool
    data:str

class RoyaltyAccount(NamedTuple):
    id:str
    wallet:str
    
