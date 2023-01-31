import time
from urllib.parse import urlencode
from asyncio import Lock
import httpx

from lnbits.extensions.pegging.kollider_rest_client.auth import auth_header
from lnbits.extensions.pegging.kollider_rest_client.data_types import Order, Ticker


class KolliderRestClient(object):
    lock = Lock()

    def __init__(
        self,
        base_url,
        api_key=None,
        secret=None,
        passphrase=None,
        jwt=None,
        jwt_refresh=None,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.jwt = jwt
        self.jwt_refresh = jwt_refresh

        # Restoring Hedge State
        with self.lock:
            r = self.get_user_account()
            if 'error' in r:
                raise Exception('Cant connect to Kollider. Check credentials')
            self._symbols = {'BTCUSD.PERP', 'BTCEUR.PERP'}
            self._balance = 0
            self._hedged = {}
            self.update_state()

    def __authorization_header(self, method, path, body=None):
        if self.secret is None and self.api_key is None and self.passphrase is None:
            header = {}
            header["authorization"] = self.jwt
            if not self.jwt:
                raise Exception("No JWT found!")
        else:
            header = auth_header(self.secret, method, path, body)
            header["k-passphrase"] = self.passphrase
            header["k-api-key"] = self.api_key
            if not self.api_key:
                raise Exception("No api key found!")
        return header

    def renew_jwt(self):
        endpoint = self.base_url + "/auth/refresh_token"
        body = {"refresh": self.jwt_refresh}
        try:
            resp = httpx.post(endpoint, json=body)
            return resp.json()
        except Exception as e:
            print(e)

    # Public Methods
    def get_tradeable_symbols(self):
        """Returns all symbols and their specification that are availble to trade."""
        endpoint = self.base_url + "/market/products"
        try:
            resp = httpx.get(endpoint)
            return resp.json()
        except Exception as e:
            print(e)

    def get_orderbook(self, symbol, level="Level2"):
        """
        Returns the orderbook for a specific symbol. NOTE: Don't long poll this. Use the
        Websockets for any real time state keeping of the Orderbook.
        params:
                symbol: <Product Symbol>
                level: Level2 | Level3
        """
        endpoint = self.base_url + "/market/orderbook?symbol={}&level={}".format(
            symbol, level
        )
        try:
            resp = httpx.get(endpoint)
            return resp.json()
        except Exception as e:
            print(e)

    def get_ticker(self, symbol) -> Ticker:
        """
        Returns the ticker for a given symbol
        params:
                symbol: <Product Symbol>
        """
        endpoint = self.base_url + "/market/ticker?symbol={}".format(symbol)
        try:
            resp = httpx.get(endpoint)
            return Ticker.from_dict(resp.json())
        except Exception as e:
            print(e)

    def get_average_funding_rates(self, start=None, end=None):
        """
        Returns current funding rates for every perp.
        """
        endpoint = self.base_url + "/market/average_funding_rates"
        if start is None:
            start = int(time.time() * 1000) - 60 * 60
        if end is None:
            end = int(time.time() * 1000)
        if end < start:
            raise Exception
        endpoint += "?start={}&end={}".format(start, end)
        try:
            resp = httpx.get(endpoint)
            return resp.json()
        except Exception as e:
            print(e)

    ### PRIVATE API ENDPOINTS

    def get_wallet_balances(self):
        """Returns users wallet balances."""
        base_path = "/user/balances"
        route = self.base_url + base_path
        try:
            headers = self.__authorization_header("GET", base_path, None)
            resp = httpx.get(route, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def get_user_account(self):
        """Returns meta data about the user account."""
        base_path = "/user/account"
        route = self.base_url + base_path
        try:
            headers = self.__authorization_header("GET", base_path, None)
            resp = httpx.get(route, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def get_historical_funding_payments(self, symbol, start=None, end=None):
        """
        Returns the historical funding payments received by a wallet.
        """
        base_path = "/user/historical_funding_payments"
        route = self.base_url + base_path
        url = {"symbol": symbol}
        if start is not None:
            url["start"] = start
        if end is not None:
            url["end"] = end
        if start and end and end < start:
            raise Exception

        query = urlencode(url)
        route += "?" + query
        auth_body = {
            "symbol": symbol if symbol else None,
            "end": end if end else None,
            "start": start if start else None,
        }

        try:
            headers = self.__authorization_header("GET", base_path, auth_body)
            resp = httpx.get(route, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def get_historical_deposits(self, network=None, limit=None, start=None, end=None):
        """
        Returns the historical deposit for a wallet.
        """
        base_path = "/user/historic_deposits"
        route = self.base_url + base_path
        auth_body = {}
        url = {}
        if start is not None:
            url["start"] = start
        if end is not None:
            url["end"] = end
        if start and end and end < start:
            raise Exception
        if limit is not None:
            url["limit"] = limit
        if network is not None:
            url["network"] = network
        query = urlencode(url)

        route += "?" + query

        auth_body = {
            "start": None if not start else start,
            "end": None if not end else end,
            "limit": None if not limit else limit,
            "network": None if not network else network,
        }

        try:
            headers = self.__authorization_header("GET", base_path, auth_body)
            resp = httpx.get(route, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def get_historical_withdrawals(
        self, network=None, limit=None, start=None, end=None
    ):
        """
        Returns the historical withdrawals for a wallet.
        """
        base_path = "/user/historic_withdrawals"
        route = self.base_url + base_path
        auth_body = {}
        url = {}
        if start is not None:
            url["start"] = start
        if end is not None:
            url["end"] = end
        if start and end and end < start:
            raise Exception
        if limit is not None:
            url["limit"] = limit
        if network is not None:
            url["network"] = network

        query = urlencode(url)
        route += "?" + query

        auth_body = {
            "start": None if not start else start,
            "end": None if not end else end,
            "limit": None if not limit else limit,
            "network": None if not network else network,
        }

        try:
            headers = self.__authorization_header("GET", base_path, auth_body)
            resp = httpx.get(route, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    # Private Method (Need valid api key)
    def get_open_orders(self):
        """Returns all currently open limit orders of a user."""
        route = "/orders/open"
        endpoint = self.base_url + route
        try:
            headers = self.__authorization_header("GET", route, None)
            resp = httpx.get(endpoint, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def get_positions(self):
        """Returns all active positions of a user."""
        route = "/positions"
        endpoint = self.base_url + route
        try:
            headers = self.__authorization_header("GET", route, None)
            resp = httpx.get(endpoint, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def make_deposit(self, amount, network="Ln"):
        """Requests a deposit"""
        route = "/wallet/deposit"
        endpoint = self.base_url + route
        body = {"type": network, "amount": amount}
        try:
            headers = self.__authorization_header("POST", route, body)
            resp = httpx.post(endpoint, json=body, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def make_withdrawal(self, amount, network="Ln", payment_request=None):
        """Requests withdrawal"""
        route = "/wallet/withdrawal"
        endpoint = self.base_url + route
        body = {"type": network, "amount": amount}
        if network == "Ln":
            if not payment_request:
                raise Exception(
                    "Need to specify a payment request on Lightning Network."
                )
            body["payment_request"] = payment_request
        try:
            headers = self.__authorization_header("POST", route, body)
            resp = httpx.post(endpoint, json=body, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def change_margin(self, action, symbol, amount):
        """Changes margin"""
        route = "/change_margin"
        endpoint = self.base_url + route
        body = {
            "amount": amount,
            "action": action,
            "symbol": symbol,
        }
        try:
            headers = self.__authorization_header("POST", route, body)
            resp = httpx.post(endpoint, json=body, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def place_order(self, order):
        route = "/orders"
        endpoint = self.base_url + route
        body = order.to_dict()
        try:
            headers = self.__authorization_header("POST", route, body)
            resp = httpx.post(endpoint, json=body, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)

    def cancel_order(self, order_id, symbol):
        route = "/orders"
        endpoint = self.base_url + route
        params = "?order_id={}&symbol={}".format(order_id, symbol)
        auth_body = {
            "order_id": order_id,
            "symbol": symbol,
        }
        endpoint += params
        try:
            headers = self.__authorization_header("DELETE", route, auth_body)
            resp = httpx.delete(endpoint, headers=headers)
            return resp.json()
        except Exception as e:
            print(e)


    def update_state(self):
        r = self.get_wallet_balances()
        self._balance = r["cash"]["SAT"]
        # r = self.get_open_orders()
        r = self.get_positions()
        for s in r.keys():
            if r[s]['side'] == 'Ask':
                self._hedged[s] = r[s]["quantity"]
            else:
                pass

    # Convenience properies and methods for hedge
    @property
    def balance(self):
        return self._balance

    @property
    def hedged(self):
        return self._hedged

    def add_hedge(self, amount: float, symbol: str):
        return self.add_position(amount, symbol, "Ask")

    def remove_hedge(self, amount: float, symbol:str):
        return self.add_position(amount, symbol, "Bid")

    def add_position(self, amount: float, symbol:str, side: str):
        t = self.get_ticker(symbol)
        order = Order(
            symbol=symbol,
            quantity=amount,
            leverage=100,
            side=side,
            price=(t.best_ask if side == "Bid" else t.best_bid),
        )
        r = self.place_order(order)
        if "error" not in r:
            print("Order placed")

