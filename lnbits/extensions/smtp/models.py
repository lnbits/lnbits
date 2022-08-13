from fastapi.params import Query
from pydantic.main import BaseModel


class CreateEmailaddress(BaseModel):
    wallet: str = Query(...)  # type: ignore
    email: str = Query(...)  # type: ignore
    testemail: str = Query(...)  # type: ignore
    smtp_server: str = Query(...)  # type: ignore
    smtp_user: str = Query(...)  # type: ignore
    smtp_password: str = Query(...)  # type: ignore
    smtp_port: str = Query(...)  # type: ignore
    description: str = Query(...)  # type: ignore
    anonymize: bool
    cost: int = Query(..., ge=0)  # type: ignore


class Emailaddresses(BaseModel):
    id: str
    wallet: str
    email: str
    testemail: str
    smtp_server: str
    smtp_user: str
    smtp_password: str
    smtp_port: str
    anonymize: bool
    description: str
    cost: int


class CreateEmail(BaseModel):
    emailaddress_id: str = Query(...)  # type: ignore
    subject: str = Query(...)  # type: ignore
    receiver: str = Query(...)  # type: ignore
    message: str = Query(...)  # type: ignore


class Emails(BaseModel):
    id: str
    wallet: str
    emailaddress_id: str
    subject: str
    receiver: str
    message: str
    paid: bool
    time: int
