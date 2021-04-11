from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids

from . import bleskomat_ext

from .exchange_rates import exchange_rate_providers_serializable, fiat_currencies
from .helpers import get_callback_url


@bleskomat_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    bleskomat_vars = {
        "callback_url": get_callback_url(),
        "exchange_rate_providers": exchange_rate_providers_serializable,
        "fiat_currencies": fiat_currencies,
    }
    return await render_template(
        "bleskomat/index.html", user=g.user, bleskomat_vars=bleskomat_vars
    )
