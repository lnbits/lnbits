from quart import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus

from . import subdomains_ext
from .crud import get_domain
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@subdomains_ext.get("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("subdomains/index.html", {"request":request,"user":g.user})


@subdomains_ext.get("/<domain_id>")
async def display(request: Request, domain_id):
    domain = await get_domain(domain_id)
    if not domain:
        abort(HTTPStatus.NOT_FOUND, "Domain does not exist.")
    allowed_records = (
        domain.allowed_record_types.replace('"', "").replace(" ", "").split(",")
    )
    print(allowed_records)
    return await templates.TemplateResponse(
        "subdomains/display.html",
        {"request":request,
        "domain_id":domain.id,
        "domain_domain":domain.domain,
        "domain_desc":domain.description,
        "domain_cost":domain.cost,
        "domain_allowed_record_types":allowed_records}
    )
