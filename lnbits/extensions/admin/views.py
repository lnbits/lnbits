from flask import g, render_template, request

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.admin import admin_ext
from lnbits.core.crud import get_admin, get_funding



@admin_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    user_id = request.args.get("usr", type=str)
    admin = get_admin()
    if admin.user != user_id:
        abort(HTTPStatus.FORBIDDEN, "Admin only")
    funding = get_funding()
    if admin[0] != None:
        admin_user = admin[0]
    if admin.user != None and admin.user != user_id:
        abort(HTTPStatus.FORBIDDEN, "Admin only")
    return render_template("admin/index.html", user=g.user, admin=admin, funding=funding)
