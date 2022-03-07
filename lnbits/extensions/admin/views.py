from quart import g, render_template, request, jsonify
import json

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.admin import admin_ext
from lnbits.core.crud import get_user, create_account
from .crud import get_admin, get_funding
from lnbits.settings import WALLET


@admin_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    user_id = g.user
    admin = await get_admin()
    
    funding = [{**funding._asdict()} for funding in await get_funding()]

    return await render_template("admin/index.html", user=g.user, admin=admin, funding=funding)
