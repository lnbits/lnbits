from fastapi import APIRouter

from .db import core_app_extra, db
from .views.admin_api import admin_router
from .views.api import api_router

# this compat is needed for usermanager extension
from .views.generic import generic_router, update_user_extension
from .views.node_api import node_router, public_node_router, super_node_router
from .views.public_api import public_router
from .views.tinyurl_api import tinyurl_router

# backwards compatibility for extensions
core_app = APIRouter(tags=["Core"])


def init_core_routers(app):
    app.include_router(core_app)
    app.include_router(generic_router)
    app.include_router(public_router)
    app.include_router(api_router)
    app.include_router(node_router)
    app.include_router(super_node_router)
    app.include_router(public_node_router)
    app.include_router(admin_router)
    app.include_router(tinyurl_router)
