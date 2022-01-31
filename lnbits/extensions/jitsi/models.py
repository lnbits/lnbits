from pydantic import BaseModel

class Conference(BaseModel):
    name: str
    admin: str  
    # numberOfMessagesProcessed: int

class Participant(BaseModel):
    id: str
    conference: str
    user: str
    wallet: str

class Payment(BaseModel):
    payer:  str
    payee:  str
    amount: int
    memo:   str
