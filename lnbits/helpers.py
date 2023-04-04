from typing import Any, List, Optional, Type

import jinja2
import shortuuid
from pydantic import BaseModel
from pydantic.schema import (
    field_schema,
    get_flat_models_from_fields,
    get_model_name_map,
)

from lnbits.jinja2_templating import Jinja2Templates
from lnbits.requestvars import g
from lnbits.settings import settings

from .extension_manager import get_valid_extensions

vendored_js = [
    "/static/vendor/moment.js",
    "/static/vendor/underscore.js",
    "/static/vendor/axios.js",
    "/static/vendor/vue.js",
    "/static/vendor/vue-router.js",
    "/static/vendor/vue-qrcode-reader.browser.js",
    "/static/vendor/vue-qrcode.js",
    "/static/vendor/vue-i18n.js",
    "/static/vendor/vuex.js",
    "/static/vendor/quasar.ie.polyfills.umd.min.js",
    "/static/vendor/quasar.umd.js",
    "/static/vendor/Chart.bundle.js",
]

vendored_css = [
    "/static/vendor/quasar.css",
    "/static/vendor/Chart.css",
    "/static/vendor/vue-qrcode-reader.css",
]


def urlsafe_short_hash() -> str:
    return shortuuid.uuid()


def url_for(endpoint: str, external: Optional[bool] = False, **params: Any) -> str:
    base = g().base_url if external else ""
    url_params = "?"
    for key, value in params.items():
        url_params += f"{key}={value}&"
    url = f"{base}{endpoint}{url_params}"
    return url


def template_renderer(additional_folders: Optional[List] = None) -> Jinja2Templates:

    folders = ["lnbits/templates", "lnbits/core/templates"]
    if additional_folders:
        folders.extend(additional_folders)
    t = Jinja2Templates(loader=jinja2.FileSystemLoader(folders))

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
    t.env.globals["LNBITS_VERSION"] = settings.lnbits_commit
    t.env.globals["LNBITS_ADMIN_UI"] = settings.lnbits_admin_ui
    t.env.globals["EXTENSIONS"] = [
        e
        for e in get_valid_extensions()
        if e.code not in settings.lnbits_deactivated_extensions
    ]
    if settings.lnbits_custom_logo:
        t.env.globals["USE_CUSTOM_LOGO"] = settings.lnbits_custom_logo

    if settings.debug:
        t.env.globals["VENDORED_JS"] = vendored_js
        t.env.globals["VENDORED_CSS"] = vendored_css
    else:
        t.env.globals["VENDORED_JS"] = ["/static/bundle.js"]
        t.env.globals["VENDORED_CSS"] = ["/static/bundle.css"]

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
    except:
        ext_name = extension_director_name
    return ext_name


def generate_filter_params_openapi(model: Type[BaseModel], keep_optional=False):
    """
    Generate openapi documentation for Filters. This is intended to be used along parse_filters (see example)
    :param model: Filter model
    :param keep_optional: If false, all parameters will be optional, otherwise inferred from model
    """
    fields = list(model.__fields__.values())
    models = get_flat_models_from_fields(fields, set())
    namemap = get_model_name_map(models)
    params = []
    for field in fields:
        schema, definitions, _ = field_schema(field, model_name_map=namemap)

        # Support nested definition
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            schema = definitions[name]

        description = "Supports Filtering"
        if schema["type"] == "object":
            description += f". Nested attributes can be filtered too, e.g. `{field.alias}.[additional].[attributes]`"

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
