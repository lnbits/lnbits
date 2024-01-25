import json
from pathlib import Path
from typing import Any, List, Optional, Type

import jinja2
import shortuuid
from pydantic import BaseModel
from pydantic.schema import field_schema

from lnbits.jinja2_templating import Jinja2Templates
from lnbits.nodes import get_node_class
from lnbits.requestvars import g
from lnbits.settings import settings

from .db import FilterModel
from .extension_manager import get_valid_extensions


def urlsafe_short_hash() -> str:
    return shortuuid.uuid()


def url_for(endpoint: str, external: Optional[bool] = False, **params: Any) -> str:
    base = g().base_url if external else ""
    url_params = "?"
    for key, value in params.items():
        url_params += f"{key}={value}&"
    url = f"{base}{endpoint}{url_params}"
    return url


def static_url_for(static: str, path: str) -> str:
    return f"/{static}/{path}?v={settings.server_startup_time}"


def template_renderer(additional_folders: Optional[List] = None) -> Jinja2Templates:
    folders = ["lnbits/templates", "lnbits/core/templates"]
    if additional_folders:
        additional_folders += [
            Path(settings.lnbits_extensions_path, "extensions", f)
            for f in additional_folders
        ]
        folders.extend(additional_folders)
    t = Jinja2Templates(loader=jinja2.FileSystemLoader(folders))
    t.env.globals["static_url_for"] = static_url_for

    if settings.lnbits_ad_space_enabled:
        t.env.globals["AD_SPACE"] = settings.lnbits_ad_space.split(",")
        t.env.globals["AD_SPACE_TITLE"] = settings.lnbits_ad_space_title

    t.env.globals["VOIDWALLET"] = settings.lnbits_backend_wallet_class == "VoidWallet"
    t.env.globals["HIDE_API"] = settings.lnbits_hide_api
    t.env.globals["SITE_TITLE"] = settings.lnbits_site_title
    t.env.globals["LNBITS_DENOMINATION"] = settings.lnbits_denomination
    t.env.globals["SITE_TAGLINE"] = settings.lnbits_site_tagline
    t.env.globals["SITE_DESCRIPTION"] = settings.lnbits_site_description
    t.env.globals["LNBITS_THEME_OPTIONS"] = settings.lnbits_theme_options
    t.env.globals["LNBITS_QR_LOGO"] = settings.lnbits_qr_logo
    t.env.globals["LNBITS_VERSION"] = settings.version
    t.env.globals["LNBITS_NEW_ACCOUNTS_ALLOWED"] = settings.new_accounts_allowed
    t.env.globals["LNBITS_ADMIN_UI"] = settings.lnbits_admin_ui
    t.env.globals["LNBITS_SERVICE_FEE"] = settings.lnbits_service_fee
    t.env.globals["LNBITS_SERVICE_FEE_MAX"] = settings.lnbits_service_fee_max
    t.env.globals["LNBITS_SERVICE_FEE_WALLET"] = settings.lnbits_service_fee_wallet
    t.env.globals["LNBITS_NODE_UI"] = (
        settings.lnbits_node_ui and get_node_class() is not None
    )
    t.env.globals["LNBITS_NODE_UI_AVAILABLE"] = get_node_class() is not None
    t.env.globals["EXTENSIONS"] = [
        e
        for e in get_valid_extensions()
        if e.code not in settings.lnbits_deactivated_extensions
    ]
    if settings.lnbits_custom_logo:
        t.env.globals["USE_CUSTOM_LOGO"] = settings.lnbits_custom_logo

    if settings.bundle_assets:
        t.env.globals["INCLUDED_JS"] = ["bundle.min.js"]
        t.env.globals["INCLUDED_CSS"] = ["bundle.min.css"]
    else:
        vendor_filepath = Path(settings.lnbits_path, "static", "vendor.json")
        with open(vendor_filepath) as vendor_file:
            vendor_files = json.loads(vendor_file.read())
            t.env.globals["INCLUDED_JS"] = vendor_files["js"]
            t.env.globals["INCLUDED_CSS"] = vendor_files["css"]

    t.env.globals["WEBPUSH_PUBKEY"] = settings.lnbits_webpush_pubkey

    return t


def get_current_extension_name() -> str:
    """
    Returns the name of the extension that calls this method.
    """
    import inspect
    import json
    import os

    callee_filepath = inspect.stack()[1].filename
    callee_dirname, _ = os.path.split(callee_filepath)

    path = os.path.normpath(callee_dirname)
    extension_director_name = path.split(os.sep)[-1]
    try:
        config_path = os.path.join(callee_dirname, "config.json")
        with open(config_path) as json_file:
            config = json.load(json_file)
        ext_name = config["name"]
    except Exception:
        ext_name = extension_director_name
    return ext_name


def generate_filter_params_openapi(model: Type[FilterModel], keep_optional=False):
    """
    Generate openapi documentation for Filters. This is intended to be used along
    parse_filters (see example)
    :param model: Filter model
    :param keep_optional: If false, all parameters will be optional,
    otherwise inferred from model
    """
    fields = list(model.__fields__.values())
    params = []
    for field in fields:
        schema, _, _ = field_schema(field, model_name_map={})

        description = "Supports Filtering"
        if (
            hasattr(model, "__search_fields__")
            and field.name in model.__search_fields__
        ):
            description += ". Supports Search"

        parameter = {
            "name": field.alias,
            "in": "query",
            "required": field.required if keep_optional else False,
            "schema": schema,
            "description": description,
        }
        params.append(parameter)

    return {
        "parameters": params,
    }


def insert_query(table_name: str, model: BaseModel) -> str:
    """
    Generate an insert query with placeholders for a given table and model
    :param table_name: Name of the table
    :param model: Pydantic model
    """
    placeholders = ", ".join(["?"] * len(model.dict().keys()))
    fields = ", ".join(model.dict().keys())
    return f"INSERT INTO {table_name} ({fields}) VALUES ({placeholders})"


def update_query(table_name: str, model: BaseModel, where: str = "WHERE id = ?") -> str:
    """
    Generate an update query with placeholders for a given table and model
    :param table_name: Name of the table
    :param model: Pydantic model
    :param where: Where string, default to `WHERE id = ?`
    """
    query = ", ".join([f"{field} = ?" for field in model.dict().keys()])
    return f"UPDATE {table_name} SET {query} {where}"
