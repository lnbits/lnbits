
from pydantic import BaseModel


class Target(BaseModel):
    wallet: str
    source: str
    percent: int
    alias: str
