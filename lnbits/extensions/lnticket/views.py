from quart import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus

from lnbits.extensions.lnticket import lnticket_ext
from .crud import get_form


@lnticket_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("lnticket/index.html", user=g.user)


@lnticket_ext.route("/<form_id>")
async def display(form_id):
    form = get_form(form_id) or abort(HTTPStatus.NOT_FOUND, "LNTicket does not exist.")
    print(form.id)

    return await render_template(
        "lnticket/display.html",
        form_id=form.id,
        form_name=form.name,
        form_desc=form.description,
        form_costpword=form.costpword,
    )
