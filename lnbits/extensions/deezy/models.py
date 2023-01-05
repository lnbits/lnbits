from pydantic.main import BaseModel
from sqlalchemy.engine import base  # type: ignore


class Token(BaseModel):
    deezy_token: str
