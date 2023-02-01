from typing import Optional, List, Mapping

from loguru import logger


class Order(object):
    """
    Order object
            side:Bid | Ask
            margin_type:Isolated | More comming (maybe)
            settlement_type:Instant | Delayed
            price:unsigned int
            quantity:unsigned int
            leverage:unsigned int
    """

    symbol: str = ""
    quantity: int = 1
    leverage: int = 100
    side: str = "Bid"
    price: int = 400000
    # ext_order_id:str = str(uuid.uuid4())
    order_type: str = "Limit"
    margin_type: str = "Isolated"
    settlement_type: str = "Instant"

    def __init__(self, symbol, quantity, leverage, side, price):
        self.symbol = symbol
        self.quantity = int(quantity)
        self.leverage = int(leverage)
        self.side = side
        self.price = int(price)

    def to_dict(self):
        return {
            "price": self.price,
            "order_type": self.order_type,
            "side": self.side,
            "quantity": self.quantity,
            "symbol": self.symbol,
            "leverage": self.leverage,
            # "ext_order_id":self.ext_order_id,
            "margin_type": self.margin_type,
            "settlement_type": self.settlement_type,
        }


class Position(object):
    uid: int = 1
    position_id: str = "a677b7f7-c2a5-493a-82d1-4ad7981130ff"
    timestamp: int = 1675254845248
    entry_time: Optional[int] = None
    symbol: str = "BTCUSD.PERP"
    upnl: float = 0.0
    rpnl: float = 0.0
    funding: float = 0.0
    leverage: float = 0.0
    real_leverage: float = 0.0
    entry_price: float = 0.0
    side: Optional[str] = None
    quantity: int = 0
    liq_price: float = 0.0
    bankruptcy_price: float = 0.0
    open_order_ids: List[int] = [142019987]
    is_liquidating: bool = False
    entry_value: float = 0.0
    mark_value: float = 0.0
    adl_score: float = 0.0

    def __init__(
        self,
        uid,
        position_id,
        timestamp,
        entry_time,
        symbol,
        upnl,
        rpnl,
        funding,
        leverage,
        real_leverage,
        entry_price,
        side,
        quantity,
        liq_price,
        bankruptcy_price,
        open_order_ids,
        is_liquidating,
        entry_value,
        mark_value,
        adl_score,
    ):
        self.uid = int(uid)
        self.position_id = str(position_id)
        self.timestamp = int(timestamp)
        self.entry_time = entry_time
        self.symbol = str(symbol)
        self.upnl = float(upnl)
        self.rpnl = float(rpnl)
        self.funding = float(funding)
        self.leverage = float(leverage)
        self.real_leverage = float(real_leverage)
        self.entry_price = float(entry_price)
        self.side = side
        self.quantity = int(quantity)
        self.liq_price = float(liq_price)
        self.bankruptcy_price = float(bankruptcy_price)
        self.open_order_ids = open_order_ids
        self.is_liquidating = is_liquidating
        self.entry_value = float(entry_value)
        self.mark_value = float(mark_value)
        self.adl_score = float(adl_score)

    @classmethod
    def from_dict(cls, source: dict):
        try:
            for k, v in source.items():
                setattr(cls, k, v)
            return cls
        except Exception as e:
            logger.error(f"{e} while reading Position object")


class Positions(object):
    def __init__(
        self,
        source,
    ):
        for k, v in source.items():
            setattr(self, k, Position.from_dict(v))

    @classmethod
    def from_dict(cls, source: dict):
        try:
            for k, v in source.items():
                setattr(cls, k, Position.from_dict(v))
            return cls
        except Exception as e:
            logger.error(f"{e} while reading Positions object")


class Ticker(object):
    best_ask: float = 1.0
    best_bid: float = 1.0
    last_price: float = 0.0
    last_quantity: int = 0
    last_side: str = "Bid"
    symbol: str = "BTCEUR.PERP"

    def __init__(
        self, best_ask, best_bid, last_price, last_quantity, last_side, symbol
    ):
        self.symbol = symbol
        self.best_ask = float(best_ask)
        self.best_bid = float(best_bid)
        self.last_price = float(last_price)
        self.last_quantity = int(last_quantity)
        self.last_side = last_side

    @classmethod
    def from_dict(cls, source: dict):
        try:
            return cls(
                source["best_ask"],
                source["best_bid"],
                source["last_price"],
                source["last_quantity"],
                source["last_side"],
                source["symbol"],
            )
        except Exception as e:
            print(f"Error {e} while reading Ticker object")


if __name__ in "__main__":
    import json

    position_str = (
        "{"
        '"uid":688,'
        '"position_id":"a677b7f7-c2a5-493a-82d1-4ad7981130ff",'
        '"timestamp": 1675254845248,'
        '"entry_time": null,'
        '"symbol": "BTCUSD.PERP",'
        '"upnl": "0",'
        '"rpnl": "0",'
        '"funding": "0",'
        '"leverage": "1.00",'
        '"real_leverage": "0.96",'
        '"entry_price": "23078.0",'
        '"side": null,'
        '"quantity": "0",'
        '"liq_price": "922337203685477580.7",'
        '"bankruptcy_price": "922337203685477580.7",'
        '"open_order_ids": [142019987],'
        '"is_liquidating": false,'
        '"entry_value": "0",'
        '"mark_value": "0",'
        '"adl_score": "-0.0006469049768957302709792596"'
        "}"
    )
    source = json.loads(position_str)
    positions_str = (
        '{"BTCUSD.PERP":'
        "{"
        '"uid":688,'
        '"position_id":"a677b7f7-c2a5-493a-82d1-4ad7981130ff",'
        '"timestamp": 1675254845248,'
        '"entry_time": null,'
        '"symbol": "BTCUSD.PERP",'
        '"upnl": "0",'
        '"rpnl": "0",'
        '"funding": "0",'
        '"leverage": "1.00",'
        '"real_leverage": "0.96",'
        '"entry_price": "23078.0",'
        '"side": null,'
        '"quantity": "0",'
        '"liq_price": "922337203685477580.7",'
        '"bankruptcy_price": "922337203685477580.7",'
        '"open_order_ids": [142019987],'
        '"is_liquidating": false,'
        '"entry_value": "0",'
        '"mark_value": "0",'
        '"adl_score": "-0.0006469049768957302709792596"'
        "}}"
    )
    source = json.loads(positions_str)
    p = Positions.from_dict(source)

"""
{'BTCUSD.PERP': [{'order_id': 142042324, 'uid': 688, 'price': 229950, 'timestamp': 1675273317381, 'filled': 0, 'ext_order_id': 'd7cad4ad-75a6-4de5-9549-98de337ee718', 'order_type': 'Limit', 'advanced_order_type': None, 'trigger_price_type': None, 'side': 'Bid', 'quantity': 22, 'symbol': 'BTCUSD.PERP', 'leverage': 100, 'margin_type': 'Isolated', 'settlement_type': 'Instant', 'origin': None}]}
"""
