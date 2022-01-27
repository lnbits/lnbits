import json
from lib2to3.pytree import Base
from sqlite3 import Row
from typing import Dict, Optional
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse

from fastapi.param_functions import Query
from lnurl.types import LnurlPayMetadata  # type: ignore
from pydantic import BaseModel
from starlette.requests import Request

from lnbits.lnurl import encode as lnurl_encode  # type: ignore


class Stalls(BaseModel):
    id: str = Query(None)
    wallet: str = Query(None)
    name: str = Query(None)
    publickey: str = Query(None)
    privatekey: str = Query(None)
    relays: str = Query(None)

class createStalls(BaseModel):
    wallet: str = Query(None)
    name: str = Query(None)
    publickey: str = Query(None)
    privatekey: str = Query(None)
    relays: str = Query(None)
    shippingzones: str = Query(None)

class createProduct(BaseModel):
    stall: str = Query(None)
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
    cost: str = Query(None)
    countries: str = Query(None)

class Zones(BaseModel):
    id: str
    wallet: str
    cost: str
    countries: str


class Orders(BaseModel):
    id: str = Query(None)
    productid: str = Query(None)
    stall: str = Query(None)
    product: str = Query(None)
    quantity: int = Query(0)
    shippingzone: int = Query(0)
    address: str = Query(None)
    email: str = Query(None)
    invoiceid: str = Query(None)
    paid: bool
    shipped: bool
