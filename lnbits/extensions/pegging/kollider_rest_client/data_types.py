from loguru import logger


class Order(object):
    """
    Order object
            side: Bid | Ask
            margin_type: Isolated | More comming (maybe)
            settlement_type: Instant | Delayed
            price: unsigned int
            quantity: unsigned int
            leverage: unsigned int
    """

    symbol: str = ""
    quantity: int = 1
    leverage: int = 100
    side: str = "Bid"
    price: int = 400000
    # ext_order_id: str = str(uuid.uuid4())
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
            # "ext_order_id": self.ext_order_id,
            "margin_type": self.margin_type,
            "settlement_type": self.settlement_type,
        }


class Ticker(object):
    best_ask: float = 1.
    best_bid: float = 1.
    last_price: float = 0.
    last_quantity: int = 0
    last_side: str = "Bid"
    symbol: str = "BTCEUR.PERP"

    def __init__(
        self, best_ask, best_bid, last_price, last_quantity, last_side, symbol
    ):
        self.best_ask = float(best_ask)
        self.best_bid = float(best_bid)
        self.last_price = float(last_price)
        self.last_quantity = int(last_quantity)
        self.last_side = last_side
        self.symbol = symbol

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
            logger.error(f"{e} while reading Ticker object")
