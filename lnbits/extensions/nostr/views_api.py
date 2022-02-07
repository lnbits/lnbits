from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.extensions.nostr import nostr_ext
from lnbits.utils.exchange_rates import currencies

from . import nostr_ext
from .crud import (
    create_nostrkeys,
    get_nostrkeys,
    create_nostrnotes,
    get_nostrnotes,
    create_nostrrelays,
    get_nostrrelays,
    create_nostrconnections,
    get_nostrconnections,
)
from .models import nostrKeys