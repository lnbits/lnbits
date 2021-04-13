from quart import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus

from . import subdomains_ext
from .crud import get_domain


@subdomains_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("subdomains/index.html", user=g.user)


@subdomains_ext.route("/<domain_id>")
async def display(domain_id):
    domain = await get_domain(domain_id)
    if not domain:
        abort(HTTPStatus.NOT_FOUND, "Domain does not exist.")
    allowed_records = (
        domain.allowed_record_types.replace('"', "").replace(" ", "").split(",")
    )
    print(allowed_records)
    return await render_template(
        "subdomains/display.html",
        domain_id=domain.id,
        domain_domain=domain.domain,
        domain_desc=domain.description,
        domain_cost=domain.cost,
        domain_allowed_record_types=allowed_records,
    )
