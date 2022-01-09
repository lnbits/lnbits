from fastapi.params import Query
from pydantic.main import BaseModel

class CreateEmailaddress(BaseModel):
    wallet: str = Query(...)
    email: str = Query(...)
    testemail: str = Query(...)
    smtp_server: str = Query(...)
    smtp_user: str = Query(...)
    smtp_password: str = Query(...)
    smtp_port: str = Query(...)
    description: str = Query(...)
    anonymize: bool
    cost: int = Query(..., ge=0)

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
    emailaddress_id: str = Query(...)
    subject: str = Query(...)
    receiver: str = Query(...)
    message: str = Query(...)

class Emails(BaseModel):
    id: str
    wallet: str
    emailaddress_id: str
    subject: str
    receiver: str
    message: str
    paid: bool
    time: int
