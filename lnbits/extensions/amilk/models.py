from pydantic import BaseModel


class AMilk(BaseModel):
    id: str
    wallet: str
    lnurl: str
    atime: int
    amount: int
