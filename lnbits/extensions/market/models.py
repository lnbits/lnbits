from typing import List, Optional

from fastapi.param_functions import Query
from pydantic import BaseModel


class MarketSettings(BaseModel):
    user: str
    currency: str
    fiat_base_multiplier: int


class SetSettings(BaseModel):
    currency: str
    fiat_base_multiplier: int = Query(100, ge=1)


class Stalls(BaseModel):
    id: str
    wallet: str
    name: str
    currency: str
    publickey: Optional[str]
    relays: Optional[str]
    shippingzones: str


class createStalls(BaseModel):
    wallet: str = Query(...)
    name: str = Query(...)
    currency: str = Query("sat")
    publickey: str = Query(None)
    relays: str = Query(None)
    shippingzones: str = Query(...)


class createProduct(BaseModel):
    stall: str = Query(...)
    product: str = Query(...)
    categories: str = Query(None)
    description: str = Query(None)
    image: str = Query(None)
    price: float = Query(0, ge=0)
    quantity: int = Query(0, ge=0)


class Products(BaseModel):
    id: str
    stall: str
    product: str
    categories: Optional[str]
    description: Optional[str]
    image: Optional[str]
    price: float
    quantity: int


class createZones(BaseModel):
    cost: float = Query(0, ge=0)
    countries: str = Query(...)


class Zones(BaseModel):
    id: str
    user: str
    cost: float
    countries: str


class OrderDetail(BaseModel):
    id: str
    order_id: str
    product_id: str
    quantity: int


class createOrderDetails(BaseModel):
    product_id: str = Query(...)
    quantity: int = Query(..., ge=1)


class createOrder(BaseModel):
    wallet: str = Query(...)
    username: str = Query(None)
    pubkey: str = Query(None)
    shippingzone: str = Query(...)
    address: str = Query(...)
    email: str = Query(...)
    total: int = Query(...)
    products: List[createOrderDetails]


class Orders(BaseModel):
    id: str
    wallet: str
    username: Optional[str]
    pubkey: Optional[str]
    shippingzone: str
    address: str
    email: str
    total: int
    invoiceid: str
    paid: bool
    shipped: bool
    time: int


class CreateMarket(BaseModel):
    usr: str = Query(...)
    name: str = Query(None)
    stalls: List[str] = Query(...)


class Market(BaseModel):
    id: str
    usr: str
    name: Optional[str]


class CreateMarketStalls(BaseModel):
    stallid: str


class ChatMessage(BaseModel):
    id: str
    msg: str
    pubkey: str
    id_conversation: str
    timestamp: int


class CreateChatMessage(BaseModel):
    msg: str = Query(..., min_length=1)
    pubkey: str = Query(...)
    room_name: str = Query(...)
