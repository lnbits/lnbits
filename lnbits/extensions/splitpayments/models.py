from pydantic.main import BaseModel
from pydantic import BaseModel
from fastapi import FastAPI, Request
from typing import List


class Target(BaseModel):
    wallet: str
    source: str
    percent: int
    alias: str


class TargetPutList(BaseModel):
    wallet: str
    aliat: str
    percent: int


class TargetPut(BaseModel):
    targets: List[TargetPutList]
