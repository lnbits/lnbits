from pydantic import BaseModel


class TinyURL(BaseModel):
    id: str
    url: str
    endless: bool
    wallet: str
    time: float
