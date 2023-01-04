from sqlite3 import Row
from typing import Optional

from fastapi import Query
from pydantic import BaseModel


class CreateService(BaseModel):
    twitchuser: str = Query(...)
    client_id: str = Query(...)
    client_secret: str = Query(...)
    wallet: str = Query(...)
    servicename: str = Query(...)
    onchain: str = Query(None)


class CreateDonation(BaseModel):
    name: str = Query("Anonymous")
    sats: int = Query(..., ge=1)
    service: int = Query(...)
    message: str = Query("")


class ValidateDonation(BaseModel):
    id: str = Query(...)


class Donation(BaseModel):
    """A Donation simply contains all the necessary information about a
    user's donation to a streamer
    """

    id: str  # This ID always corresponds to a satspay charge ID
    wallet: str
    name: str  # Name of the donor
    message: str  # Donation message
    cur_code: str  # Three letter currency code accepted by Streamlabs
    sats: int
    amount: float  # The donation amount after fiat conversion
    service: int  # The ID of the corresponding Service
    posted: bool  # Whether the donation has already been posted to a Service

    @classmethod
    def from_row(cls, row: Row) -> "Donation":
        return cls(**dict(row))


class Service(BaseModel):
    """A Service represents an integration with a third-party API

    Currently, Streamlabs is the only supported Service.
    """

    id: int
    state: str  # A random hash used during authentication
    twitchuser: str  # The Twitch streamer's username
    client_id: str  # Third party service Client ID
    client_secret: str  # Secret corresponding to the Client ID
    wallet: str
    onchain: Optional[str]
    servicename: str  # Currently, this will just always be "Streamlabs"
    authenticated: bool  # Whether a token (see below) has been acquired yet
    token: Optional[str]  # The token with which to authenticate requests

    @classmethod
    def from_row(cls, row: Row) -> "Service":
        return cls(**dict(row))
