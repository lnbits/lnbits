from quart import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids

from . import lnaddress_ext
from .crud import get_domain, purge_addresses


@lnaddress_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("lnaddress/index.html", user=g.user)

@lnaddress_ext.route("/<domain_id>")
async def display(domain_id):
    domain = await get_domain(domain_id)
    if not domain:
        abort(HTTPStatus.NOT_FOUND, "Domain does not exist.")
        
    await purge_addresses(domain_id)

    return await render_template(
        "lnaddress/display.html",
        domain_id=domain.id,
        domain_domain=domain.domain,
        domain_cost=domain.cost
    )
