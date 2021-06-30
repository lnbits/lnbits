from typing import NamedTuple, Optional


class Setup(NamedTuple):
    usr_id: str
    invoice_wallet: str
    payout_wallet: str
    data: Optional[str]


class Users(NamedTuple):
    usr_id: str
    id: Optional[str]
    lnurl_auth: Optional[str]
    admin: str
    payout_wallet: str
    credits: int
    active: bool
    data: Optional[str]


class Logs(NamedTuple):
    usr: str
    cmd: str
    wl: Optional[str]
    credits: Optional[int]
    multi: Optional[int]
    sats: Optional[int]
    data: Optional[str]


class Payments(NamedTuple):
    id: str
    admin_id: str
    usr_id: str
    amount: int
    credits: int
    paid: bool
    cmd: str
    data: Optional[str]
