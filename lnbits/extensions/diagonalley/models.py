from typing import Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class Stalls(BaseModel):
    id: str
    wallet: str
    name: str
    publickey: Optional[str]
    privatekey: Optional[str]
    relays: Optional[str]
    shippingzones: str


class createStalls(BaseModel):
    wallet: str = Query(...)
    name: str = Query(...)
    publickey: str = Query(None)
    privatekey: str = Query(None)
    relays: str = Query(None)
    shippingzones: str = Query(...)


class createProduct(BaseModel):
    stall: str = Query(...)
    product: str = Query(None)
    categories: str = Query(None)
    description: str = Query(None)
    image: str = Query(None)
    price: int = Query(0, ge=0)
    quantity: int = Query(0, ge=0)


class Products(BaseModel):
    id: str
    stall: str
    product: str
    categories: str
    description: str
    image: str
    price: int
    quantity: int


class createZones(BaseModel):
    cost: int = Query(0, ge=0)
    countries: str = Query(...)


class Zones(BaseModel):
    id: str
    user: str
    cost: int
    countries: str


class createOrder(BaseModel):
    productid: str = Query(...)
    stall: str = Query(...)
    product: str = Query(...)
    quantity: int = Query(..., ge=1)
    shippingzone: int = Query(...)
    address: str = Query(...)
    email: str = Query(...)
    invoiceid: str = Query(...)


class Orders(BaseModel):
    id: str
    productid: str
    stall: str
    pubkey: str
    product: str
    quantity: int
    shippingzone: int
    address: str
    email: str
    invoiceid: str
    paid: bool
    shipped: bool
    time: int
