from typing import List, Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class Target(BaseModel):
    wallet: str
    source: str
    percent: float
    alias: Optional[str]


class TargetPutList(BaseModel):
    wallet: str = Query(...)
    alias: str = Query("")
    percent: float = Query(..., ge=0.01)


class TargetPut(BaseModel):
    __root__: List[TargetPutList]
