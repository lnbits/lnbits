import json
import os

from jinja2 import Environment, FileSystemLoader

from lnbits.core.models.extensions_builder import DataField, ExtensionData
from lnbits.db import dict_to_model
from lnbits.helpers import camel_to_snake

py_files = [
    "__init__.py",
    "models.py",
    "migrations.py",
    "views_api.py",
    "crud.py",
    "views.py",
    "tasks.py",
    "services.py",
]

remove_line_marker = "{remove_line_marker}}"

extra_ui_fields = [
    {
        "name": "updated_at",
        "type": "datetime",
        "label": "Updated At",
        "hint": "Timestamp of the last update",
        "optional": False,
        "editable": False,
        "searchable": False,
        "sortable": True,
    },
    {
        "name": "id",
        "type": "str",
        "label": "ID",
        "hint": "Unique identifier",
        "optional": False,
        "editable": False,
        "searchable": False,
        "sortable": True,
    },
]
ui_table_columns = [dict_to_model(f, DataField) for f in extra_ui_fields]


def jinja_env(template_dir: str) -> Environment:
    return Environment(
        loader=FileSystemLoader(template_dir),
        variable_start_string="<<",
        variable_end_string=">>",
        block_start_string="<%",
        block_end_string="%>",
        comment_start_string="<#",
        comment_end_string="#>",
        autoescape=True,
    )


def parse_extension_data(data: ExtensionData) -> dict:

    return {
        "owner_data": {
            "name": data.owner_data.name,
            "editable_fields": [
                field_to_py(field) for field in data.owner_data.fields if field.editable
            ],
            "search_fields": [
                camel_to_snake(field.name)
                for field in data.owner_data.fields
                if field.searchable
            ],
            "ui_table_columns": [
                field_to_ui_table_column(field)
                for field in data.owner_data.fields + ui_table_columns
                if field.sortable
            ],
            "db_fields": [field_to_db(field) for field in data.owner_data.fields],
            "all_fields": [field_to_py(field) for field in data.owner_data.fields],
        },
        "client_data": {
            "name": data.client_data.name,
            "editable_fields": [
                field_to_py(field)
                for field in data.client_data.fields
                if field.editable
            ],
            "search_fields": [
                camel_to_snake(field.name)
                for field in data.client_data.fields
                if field.searchable
            ],
            "ui_table_columns": [
                field_to_ui_table_column(field)
                for field in data.client_data.fields + ui_table_columns
                if field.sortable
            ],
            "db_fields": [field_to_db(field) for field in data.client_data.fields],
            "all_fields": [field_to_py(field) for field in data.client_data.fields],
        },
        "settings_data": {
            "enabled": data.settings_data.enabled,
            "is_admin_settings_only": data.settings_data.type == "admin",
            "editable_fields": [
                field_to_py(field)
                for field in data.settings_data.fields
                if field.editable
            ],
            "db_fields": [field_to_db(field) for field in data.settings_data.fields],
        },
        "public_page": data.public_page,
        "cancel_comment": remove_line_marker,
    }


def replace_jinja_placeholders(data: ExtensionData) -> None:
    parsed_data = parse_extension_data(data)
    for py_file in py_files:
        template_path = f"./{py_file}"
        rederer = render_file(template_path, parsed_data)
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(rederer)

        remove_lines_with_string(template_path, remove_line_marker)

    template_path = "./static/js/index.js"
    rederer = render_file(template_path, parsed_data)
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(rederer)

    remove_lines_with_string(template_path, remove_line_marker)

    owner_inputs = html_input_fields(
        [f for f in data.owner_data.fields if f.editable],
        "ownerDataFormDialog.data",
    )
    client_inputs = html_input_fields(
        [f for f in data.client_data.fields if f.editable],
        "clientDataFormDialog.data",
    )
    settings_inputs = html_input_fields(
        [f for f in data.settings_data.fields if f.editable],
        "settingsFormDialog.data",
    )
    template_path = "./templates/extension_builder_stub/index.html"
    rederer = render_file(
        template_path,
        {
            "extension_builder_stub_owner_inputs": owner_inputs,
            "extension_builder_stub_settings_inputs": settings_inputs,
            "extension_builder_stub_client_inputs": client_inputs,
            "cancel_comment": remove_line_marker,
            **parsed_data,
        },
    )
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(rederer)

    remove_lines_with_string(template_path, remove_line_marker)

    public_client_data_inputs = html_input_fields(
        [
            f
            for f in data.client_data.fields
            if f.name in data.public_page.client_data_fields.public_inputs
        ],
        "publicClientData",
    )
    template_path = "./templates/extension_builder_stub/public_owner_data.html"
    rederer = render_file(
        template_path,
        {
            "extension_builder_stub_public_client_inputs": public_client_data_inputs,
            "cancel_comment": remove_line_marker,
        },
    )
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(rederer)

    remove_lines_with_string(template_path, remove_line_marker)


def field_to_db(field: DataField) -> str:
    field_name = camel_to_snake(field.name)
    field_type = field.type
    if field_type == "str":
        db_type = "TEXT"
    elif field_type == "int":
        db_type = "INT"
    elif field_type == "float":
        db_type = "REAL"
    elif field_type == "bool":
        db_type = "BOOLEAN"
    elif field_type == "datetime":
        db_type = "TIMESTAMP"
    else:
        db_type = "TEXT"

    db_field = f"{field_name} {db_type}"
    if not field.optional:
        db_field += " NOT NULL"
    if field_type == "json":
        db_field += " DEFAULT '{empty_dict}'"
    return db_field


def field_to_ui_table_column(field: DataField) -> str:
    column = {
        "name": field.name,
        "align": "left",
        "label": field.label or field.name,
        "field": field.name,
        "sortable": field.sortable,
    }

    return json.dumps(column)


def html_input_fields(fields: list[DataField], model_name: str) -> str:
    template_path = "./templates/extension_builder_stub/_input_fields.html"

    rederer = render_file(
        template_path,
        {
            "fields": fields,
            "model_name": model_name,
        },
    )
    return rederer


def field_to_py(field: DataField) -> str:
    field_name = camel_to_snake(field.name)
    field_type = field.type
    if field_type == "json":
        field_type = "dict"
    elif field_type in ["wallet", "currency", "text"]:
        field_type = "str"
    if field.optional:
        field_type += " | None"
    return f"{field_name}: {field_type}"


def render_file(template_path: str, data: dict) -> str:
    # Extract directory and file name
    template_dir = os.path.dirname(template_path)
    template_file = os.path.basename(template_path)

    # Create Jinja environment
    # env = Environment(loader=FileSystemLoader(template_dir))
    env = jinja_env(template_dir)
    template = env.get_template(template_file)

    # Render the template with data
    return template.render(**data)


def remove_lines_with_string(file_path: str, target: str) -> None:
    """
    Removes lines from a file that contain the given target string.

    Args:
        file_path (str): Path to the file.
        target (str): Substring to search for in lines to remove.
    """
    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    filtered_lines = [line for line in lines if target not in line]

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(filtered_lines)
