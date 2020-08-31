from typing import NamedTuple


class Indexers(NamedTuple):
    id: str
    wallet: str
    shopname: str
    indexeraddress: str
    online: bool
    rating: str
    shippingzone1: str
    shippingzone2: str
    zone1cost: int
    zone2cost: int
    email: str


class Products(NamedTuple):
    id: str
    wallet: str
    product: str
    categories: str
    description: str
    image: str
    price: int
    quantity: int


class Orders(NamedTuple):
    id: str
    productid: str
    wallet: str
    product: str
    quantity: int
    shippingzone: int
    address: str
    email: str
    invoiceid: str
    paid: bool
    shipped: bool
