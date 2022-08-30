from enum import Enum
from sqlite3 import Row
from typing import List, Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class InvoiceStatusEnum(str, Enum):
    draft = "draft"
    open = "open"
    paid = "paid"
    canceled = "canceled"


class CreateInvoiceItemData(BaseModel):
    description: str
    amount: float = Query(..., ge=0.01)


class CreateInvoiceData(BaseModel):
    status: InvoiceStatusEnum = InvoiceStatusEnum.draft
    currency: str
    company_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    items: List[CreateInvoiceItemData]

    class Config:
        use_enum_values = True


class UpdateInvoiceItemData(BaseModel):
    id: Optional[str]
    description: str
    amount: float = Query(..., ge=0.01)


class UpdateInvoiceData(BaseModel):
    id: str
    wallet: str
    status: InvoiceStatusEnum = InvoiceStatusEnum.draft
    currency: str
    company_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    items: List[UpdateInvoiceItemData]


class Invoice(BaseModel):
    id: str
    wallet: str
    status: InvoiceStatusEnum = InvoiceStatusEnum.draft
    currency: str
    company_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    time: int

    class Config:
        use_enum_values = True

    @classmethod
    def from_row(cls, row: Row) -> "Invoice":
        return cls(**dict(row))


class InvoiceItem(BaseModel):
    id: str
    invoice_id: str
    description: str
    amount: int

    class Config:
        orm_mode = True

    @classmethod
    def from_row(cls, row: Row) -> "InvoiceItem":
        return cls(**dict(row))


class Payment(BaseModel):
    id: str
    invoice_id: str
    amount: int
    time: int

    @classmethod
    def from_row(cls, row: Row) -> "Payment":
        return cls(**dict(row))


class CreatePaymentData(BaseModel):
    invoice_id: str
    amount: int
