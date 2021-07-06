from quart import g, render_template, request

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.admin import admin_ext
from lnbits.core.crud import get_user, create_account
from .crud import get_admin, get_funding
from lnbits.settings import WALLET


@admin_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    user_id = request.args.get("usr", type=str)
    admin = await get_admin(user_id)
    funding = await get_funding()

    print('ADMIN', admin)
    print('FUNDING', funding)

    return await render_template("admin/index.html", user=g.user, admin=admin, funding=funding)
