import os
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from lnbits.core.models.extensions_builder import DataField, ExtensionData
from lnbits.db import dict_to_model
from lnbits.helpers import camel_to_snake, camel_to_words, lowercase_first_letter

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


def replace_jinja_placeholders(data: ExtensionData, ext_stub_dir: Path) -> None:
    parsed_data = _parse_extension_data(data)
    for py_file in py_files:
        template_path = Path(ext_stub_dir, py_file).as_posix()
        rederer = _render_file(template_path, parsed_data)
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(rederer)

        remove_lines_with_string(template_path, remove_line_marker)

    template_path = Path(ext_stub_dir, "static", "js", "index.js").as_posix()
    rederer = _render_file(template_path, parsed_data)
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(rederer)

    remove_lines_with_string(template_path, remove_line_marker)

    owner_inputs = html_input_fields(
        [f for f in data.owner_data.fields if f.editable],
        "ownerDataFormDialog.data",
        ext_stub_dir,
    )
    client_inputs = html_input_fields(
        [f for f in data.client_data.fields if f.editable],
        "clientDataFormDialog.data",
        ext_stub_dir,
    )
    settings_inputs = html_input_fields(
        [f for f in data.settings_data.fields if f.editable],
        "settingsFormDialog.data",
        ext_stub_dir,
    )
    template_path = Path(
        ext_stub_dir, "templates", "extension_builder_stub", "index.html"
    ).as_posix()
    rederer = _render_file(
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
        ext_stub_dir,
    )
    template_path = Path(
        ext_stub_dir, "templates", "extension_builder_stub", "public_owner_data.html"
    ).as_posix()
    rederer = _render_file(
        template_path,
        {
            "extension_builder_stub_public_client_inputs": public_client_data_inputs,
            "cancel_comment": remove_line_marker,
        },
    )
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(rederer)

    remove_lines_with_string(template_path, remove_line_marker)


def html_input_fields(
    fields: list[DataField], model_name: str, ext_stub_dir: Path
) -> str:
    template_path = Path(
        ext_stub_dir, "templates", "extension_builder_stub", "_input_fields.html"
    ).as_posix()

    rederer = _render_file(
        template_path,
        {
            "fields": fields,
            "model_name": model_name,
        },
    )
    return rederer


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


####### RENAME ######

excluded_dirs = {"./.", "./__pycache__", "./node_modules", "./transform"}


def rename_extension_builder_stub(data: ExtensionData, extension_dir: Path) -> None:

    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="extension_builder_stub_name",
        new_text=data.name,
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="extension_builder_stub_short_description",
        new_text=data.short_description,
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="extension_builder_stub",
        new_text=data.id,
        file_extensions=[".py", ".js", ".html", ".md", ".json", ".toml"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="OwnerData",
        new_text=data.owner_data.name,
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="ownerData",
        new_text=lowercase_first_letter(data.owner_data.name),
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="Owner Data",
        new_text=camel_to_words(data.owner_data.name),
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )

    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="owner_data",
        new_text=camel_to_snake(data.owner_data.name),
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="owner data",
        new_text=camel_to_words(data.owner_data.name).lower(),
        file_extensions=[".py"],
    )

    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="ClientData",
        new_text=data.client_data.name,
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="clientData",
        new_text=lowercase_first_letter(data.client_data.name),
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="Client Data",
        new_text=camel_to_words(data.client_data.name),
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )

    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="client_data",
        new_text=camel_to_snake(data.client_data.name),
        file_extensions=[".py", ".js", ".html", ".md", ".json"],
    )
    replace_text_in_files(
        directory=extension_dir.as_posix(),
        old_text="client data",
        new_text=camel_to_words(data.client_data.name).lower(),
        file_extensions=[".py"],
    )

    rename_files_and_dirs_in_directory(
        directory=extension_dir.as_posix(),
        old_text="extension_builder_stub",
        new_text=data.id,
    )
    rename_files_and_dirs_in_directory(
        directory=extension_dir.as_posix(),
        old_text="owner_data",
        new_text=camel_to_snake(data.owner_data.name),
    )

    # zip_directory(".", data.id + ".zip")


def replace_text_in_files(directory, old_text, new_text, file_extensions=None):
    """
    Recursively replaces text in all files under the given directory.

    Parameters:
    - directory (str): Root directory to start searching.
    - old_text (str): Text to search for.
    - new_text (str): Text to replace with.
    - file_extensions (list[str], optional): Only process files with these extensions.
    """
    for root, _, files in os.walk(directory):
        if _is_excluded_dir(root):
            continue

        for filename in files:
            if file_extensions:
                if not any(filename.endswith(ext) for ext in file_extensions):
                    continue

            file_path = os.path.join(root, filename)
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                if old_text in content:
                    new_content = content.replace(old_text, new_text)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    logger.trace(f"Updated: {file_path}")
            except (UnicodeDecodeError, PermissionError, FileNotFoundError) as e:
                logger.debug(f"Skipped {file_path}: {e}")


def rename_files_and_dirs_in_directory(directory, old_text, new_text):
    """
    Recursively renames files and directories by replacing part of their names.

    Parameters:
    - directory (str): Root directory to start renaming.
    - old_text (str): Text to be replaced.
    - new_text (str): Text to replace with.
    """
    # First rename directories (bottom-up) so we don't lose paths while renaming
    for root, dirs, files in os.walk(directory, topdown=False):
        if _is_excluded_dir(root):
            continue
        # Rename files
        for filename in files:
            if old_text in filename:
                old_path = os.path.join(root, filename)
                new_filename = filename.replace(old_text, new_text)
                new_path = os.path.join(root, new_filename)
                try:
                    os.rename(old_path, new_path)
                    logger.trace(f"Renamed file: {old_path} -> {new_path}")
                except Exception as e:
                    logger.warning(f"Failed to rename file {old_path}: {e}")

        # Rename directories
        for dirname in dirs:
            if old_text in dirname:
                old_dir_path = os.path.join(root, dirname)
                new_dir_name = dirname.replace(old_text, new_text)
                new_dir_path = os.path.join(root, new_dir_name)
                try:
                    os.rename(old_dir_path, new_dir_path)
                    logger.trace(f"Renamed directory: {old_dir_path} -> {new_dir_path}")
                except Exception as e:
                    logger.warning(f"Failed to rename directory {old_dir_path}: {e}")


def zip_directory(source_dir, zip_path):
    """
    Zips the contents of a directory (including subdirectories and files).

    Parameters:
    - source_dir (str): The path of the directory to zip.
    - zip_path (str): The path where the .zip file will be saved.
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            if _is_excluded_dir(root):
                continue

            for file in files:
                full_path = os.path.join(root, file)
                # Add file with a relative path inside the zip
                relative_path = os.path.relpath(full_path, start=source_dir)
                zipf.write(full_path, arcname=relative_path)


def _render_file(template_path: str, data: dict) -> str:
    # Extract directory and file name
    template_dir = os.path.dirname(template_path)
    template_file = os.path.basename(template_path)

    # Create Jinja environment
    # env = Environment(loader=FileSystemLoader(template_dir))
    env = _jinja_env(template_dir)
    template = env.get_template(template_file)

    # Render the template with data
    return template.render(**data)


def _jinja_env(template_dir: str) -> Environment:
    return Environment(
        loader=FileSystemLoader(template_dir),
        variable_start_string="<<",
        variable_end_string=">>",
        block_start_string="<%",
        block_end_string="%>",
        comment_start_string="<#",
        comment_end_string="#>",
        autoescape=False,
    )


def _parse_extension_data(data: ExtensionData) -> dict:

    return {
        "owner_data": {
            "name": data.owner_data.name,
            "editable_fields": [
                field.field_to_py()
                for field in data.owner_data.fields
                if field.editable
            ],
            "search_fields": [
                camel_to_snake(field.name)
                for field in data.owner_data.fields
                if field.searchable
            ],
            "ui_table_columns": [
                field.field_to_ui_table_column()
                for field in data.owner_data.fields + ui_table_columns
                if field.sortable
            ],
            "db_fields": [field.field_to_db() for field in data.owner_data.fields],
            "all_fields": [field.field_to_py() for field in data.owner_data.fields],
        },
        "client_data": {
            "name": data.client_data.name,
            "editable_fields": [
                field.field_to_py()
                for field in data.client_data.fields
                if field.editable
            ],
            "search_fields": [
                camel_to_snake(field.name)
                for field in data.client_data.fields
                if field.searchable
            ],
            "ui_table_columns": [
                field.field_to_ui_table_column()
                for field in data.client_data.fields + ui_table_columns
                if field.sortable
            ],
            "db_fields": [field.field_to_db() for field in data.client_data.fields],
            "all_fields": [field.field_to_py() for field in data.client_data.fields],
        },
        "settings_data": {
            "enabled": data.settings_data.enabled,
            "is_admin_settings_only": data.settings_data.type == "admin",
            "editable_fields": [
                field.field_to_py()
                for field in data.settings_data.fields
                if field.editable
            ],
            "db_fields": [field.field_to_db() for field in data.settings_data.fields],
        },
        "public_page": data.public_page,
        "cancel_comment": remove_line_marker,
    }


def _is_excluded_dir(path):
    for excluded_dir in excluded_dirs:
        if path.startswith(excluded_dir):
            return True
    return False
