from quart import g, render_template, request

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.admin import admin_ext
from lnbits.core.crud import get_admin, get_funding, get_user, create_account
from lnbits.settings import WALLET


@admin_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    user_id = request.args.get("usr", type=str)
    print(user_id)
    admin = get_admin()
    if admin != None:
        if admin[0] == None:
            admin_user = get_user(create_account().id).id
        if admin.user != user_id:
            abort(HTTPStatus.FORBIDDEN, "Admin only")
        if not user_id:
            admin_user = get_user(create_account().id).id
            print(admin_user)
            admin = get_admin()
        else:
            admin_user = user_id
            
    funding = get_funding()

    return render_template("admin/index.html", user=g.user, admin=admin, funding=funding)
