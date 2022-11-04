from sqlite3 import Row
from typing import Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class Schedule(BaseModel):
    id: str
    wallet: str
    recipient: str
    famount: int
    currency: str
    interval: str
    timezone: str
    start_date: Optional[str]
    end_date: Optional[str]
    time: int

    @classmethod
    def from_row(cls, row: Row) -> "Schedule":
        return cls(**dict(row))


class ScheduleEvent(BaseModel):
    id: str
    schedule_id: str
    amount: int
    payment_hash: Optional[str]
    time: int
    status: str

    class Config:
        orm_mode = True

    @classmethod
    def from_row(cls, row: Row) -> "ScheduleEvent":
        return cls(**dict(row))


class CreateScheduleData(BaseModel):
    wallet: str
    recipient: str
    famount: float = Query(..., ge=0.01)
    currency: str
    interval: str
    timezone: str
    start_date: Optional[str]
    end_date: Optional[str]


class UpdateScheduleData(BaseModel):
    id: str
    wallet: str
    recipient: str
    famount: float = Query(..., ge=0.01)
    currency: str
    interval: str
    timezone: str
    start_date: Optional[str]
    end_date: Optional[str]


class CreateScheduleEventData(BaseModel):
    schedule_id: str
    amount: int
    payment_hash: Optional[str]
    time: int
    status: str


class UpdateScheduleEventData(BaseModel):
    id: str
    schedule_id: str
    amount: int
    payment_hash: Optional[str]
    time: int
    status: str
