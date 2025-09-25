import asyncio
import json
import os
import shutil
import zipfile
from hashlib import sha256
from pathlib import Path
from time import time
from uuid import uuid4

import shortuuid
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from lnbits.core.models.extensions import ExtensionRelease, InstallableExtension
from lnbits.core.models.extensions_builder import DataField, ExtensionData
from lnbits.db import dict_to_model
from lnbits.helpers import (
    camel_to_snake,
    camel_to_words,
    download_url,
    lowercase_first_letter,
)
from lnbits.settings import settings

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

ui_table_columns = [
    DataField(
        name="updated_at",
        type="datetime",
        label="Updated At",
        hint="Timestamp of the last update",
        optional=False,
        editable=False,
        searchable=False,
        sortable=True,
    ),
    DataField(
        name="id",
        type="str",
        label="ID",
        hint="Unique identifier",
        optional=False,
        editable=False,
        searchable=False,
        sortable=True,
    ),
]


excluded_dirs = {"./.", "./__pycache__", "./node_modules", "./transform"}


async def build_extension_from_data(
    data: ExtensionData, stub_ext_id: str, working_dir_name: str | None = None
):
    release = await _get_extension_stub_release(stub_ext_id, data.stub_version)
    release.hash = sha256(uuid4().hex.encode("utf-8")).hexdigest()
    release.icon = f"/{data.id}/static/image/{data.id}.png"
    release.is_github_release = False
    await _fetch_extension_builder_stub(stub_ext_id, release)
    build_dir = _copy_ext_stub_to_build_dir(
        stub_ext_id=stub_ext_id,
        stub_version=release.version,
        new_ext_id=data.id,
        working_dir_name=working_dir_name,
    )
    _transform_extension_builder_stub(data, build_dir)
    _export_extension_data_json(data, build_dir)
    return release, build_dir


def clean_extension_builder_data() -> None:
    working_dir = Path(settings.extension_builder_working_dir_path)
    if working_dir.is_dir():
        shutil.rmtree(working_dir, True)
    working_dir.mkdir(parents=True, exist_ok=True)


def _transform_extension_builder_stub(data: ExtensionData, extension_dir: Path) -> None:
    _replace_jinja_placeholders(data, extension_dir)
    _rename_extension_builder_stub(data, extension_dir)


def _export_extension_data_json(data: ExtensionData, build_dir: Path):
    json.dump(
        data.dict(),
        open(Path(build_dir, "builder.json"), "w", encoding="utf-8"),
        indent=4,
    )


async def _get_extension_stub_release(
    stub_ext_id: str, stub_version: str | None = None
) -> ExtensionRelease:
    working_dir = Path(settings.extension_builder_working_dir_path, stub_ext_id)
    cache_dir = Path(working_dir, f"cache-{stub_version}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    release_cache_file = Path(cache_dir, "release.json")

    if stub_version:
        cached_release = _load_extension_stub_release_from_cache(
            stub_ext_id, stub_version
        )
        if cached_release:
            logger.debug(f"Loading release from cache {stub_ext_id} ({stub_version}).")
            return cached_release

    releases: list[ExtensionRelease] = (
        await InstallableExtension.get_extension_releases(stub_ext_id)
    )

    release = next((r for r in releases if r.version == stub_version), None)

    if not release and len(releases) > 0:
        release = releases[0]

    if not release:
        raise ValueError(f"Release {stub_ext_id} ({stub_version}) not found.")

    logger.debug(f"Save release cache {stub_ext_id} ({stub_version}).")
    with open(release_cache_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(release.dict(), indent=4))

    return release


def _load_extension_stub_release_from_cache(
    stub_ext_id: str, stub_version: str
) -> ExtensionRelease | None:
    working_dir = Path(settings.extension_builder_working_dir_path, stub_ext_id)
    cache_dir = Path(working_dir, f"cache-{stub_version}")
    release_cache_file = Path(cache_dir, "release.json")
    if release_cache_file.is_file():
        with open(release_cache_file, encoding="utf-8") as f:
            return dict_to_model(json.load(f), ExtensionRelease)
    return None


async def _fetch_extension_builder_stub(
    stub_ext_id: str, release: ExtensionRelease
) -> Path:
    working_dir = Path(settings.extension_builder_working_dir_path, stub_ext_id)
    cache_dir = Path(working_dir, f"cache-{release.version}")
    cache_dir.mkdir(parents=True, exist_ok=True)

    stub_ext_zip_path = Path(cache_dir, release.version + ".zip")
    ext_stub_cache_dir = Path(cache_dir, stub_ext_id)

    if not stub_ext_zip_path.is_file():
        await asyncio.to_thread(download_url, release.archive_url, stub_ext_zip_path)
        shutil.rmtree(ext_stub_cache_dir, True)

    if not ext_stub_cache_dir.is_dir():
        tmp_dir = Path(cache_dir, "tmp")
        shutil.rmtree(tmp_dir, True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(stub_ext_zip_path, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)
        generated_dir = Path(tmp_dir, os.listdir(tmp_dir)[0])
        shutil.copytree(generated_dir, Path(ext_stub_cache_dir))
        shutil.rmtree(tmp_dir, True)

    return ext_stub_cache_dir


def _copy_ext_stub_to_build_dir(
    stub_ext_id: str,
    stub_version: str,
    new_ext_id: str,
    working_dir_name: str | None = None,
) -> Path:
    working_dir = Path(settings.extension_builder_working_dir_path, stub_ext_id)
    cache_dir = Path(working_dir, f"cache-{stub_version}")

    ext_stub_cache_dir = Path(cache_dir, stub_ext_id)
    if not ext_stub_cache_dir.is_dir():
        raise ValueError(
            f"Extension stub cache dir not found: {stub_ext_id} ({stub_version})"
        )

    working_dir_name = working_dir_name or f"ext-{int(time())}-{shortuuid.uuid()}"
    ext_build_dir = Path(working_dir, new_ext_id, working_dir_name, new_ext_id)
    shutil.rmtree(ext_build_dir, True)

    shutil.copytree(ext_stub_cache_dir, ext_build_dir)
    return ext_build_dir


def _replace_jinja_placeholders(data: ExtensionData, ext_stub_dir: Path) -> None:
    parsed_data = _parse_extension_data(data)
    for py_file in py_files:
        template_path = Path(ext_stub_dir, py_file).as_posix()
        rederer = _render_file(template_path, parsed_data)
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(rederer)

        _remove_lines_with_string(template_path, remove_line_marker)

    template_path = Path(ext_stub_dir, "static", "js", "index.js").as_posix()
    rederer = _render_file(
        template_path, {"preview": data.preview_action, **parsed_data}
    )
    embeded_index_js = rederer
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(rederer)

    _remove_lines_with_string(template_path, remove_line_marker)

    owner_inputs = _fields_to_html_input(
        [f for f in data.owner_data.fields if f.editable],
        "ownerDataFormDialog.data",
        ext_stub_dir,
    )
    client_inputs = _fields_to_html_input(
        [f for f in data.client_data.fields if f.editable],
        "clientDataFormDialog.data",
        ext_stub_dir,
    )
    settings_inputs = _fields_to_html_input(
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
            "embeded_index_js": embeded_index_js,
            "extension_builder_stub_owner_inputs": owner_inputs,
            "extension_builder_stub_settings_inputs": settings_inputs,
            "extension_builder_stub_client_inputs": client_inputs,
            "preview": data.preview_action,
            "cancel_comment": remove_line_marker,
            **parsed_data,
        },
    )
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(rederer)

    _remove_lines_with_string(template_path, remove_line_marker)

    public_client_inputs = _fields_to_html_input(
        [
            f
            for f in data.client_data.fields
            if f.name in data.public_page.client_data_fields.public_inputs
        ],
        "publicClientData",
        ext_stub_dir,
    )
    public_template_path = Path(
        ext_stub_dir, "templates", "extension_builder_stub", "public_page.html"
    )
    template_path = public_template_path.as_posix()
    if not data.public_page.has_public_page:
        public_template_path.unlink(missing_ok=True)
    else:
        rederer = _render_file(
            template_path,
            {
                "extension_builder_stub_public_client_inputs": public_client_inputs,
                "preview": data.preview_action,
                **data.public_page.action_fields.dict(),
                "cancel_comment": remove_line_marker,
            },
        )

        with open(template_path, "w", encoding="utf-8") as f:
            f.write(rederer)

        _remove_lines_with_string(template_path, remove_line_marker)


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


def _rename_extension_builder_stub(data: ExtensionData, extension_dir: Path) -> None:
    extension_dir_path = extension_dir.as_posix()
    rename_values = {
        "extension_builder_stub_name": data.name,
        "extension_builder_stub_short_description": data.short_description or "",
        "extension_builder_stub": data.id,
        "OwnerData": data.owner_data.name,
        "ownerData": lowercase_first_letter(data.owner_data.name),
        "Owner Data": camel_to_words(data.owner_data.name),
        "owner data": camel_to_words(data.owner_data.name).lower(),
        "owner_data": camel_to_snake(data.owner_data.name),
        "ClientData": data.client_data.name,
        "clientData": lowercase_first_letter(data.client_data.name),
        "Client Data": camel_to_words(data.client_data.name),
        "client data": camel_to_words(data.client_data.name).lower(),
        "client_data": camel_to_snake(data.client_data.name),
    }
    for old_text, new_text in rename_values.items():
        _replace_text_in_files(
            directory=extension_dir_path,
            old_text=old_text,
            new_text=new_text,
            file_extensions=[".py", ".js", ".html", ".md", ".json", ".toml"],
        )

    _rename_files_and_dirs_in_directory(
        directory=extension_dir_path,
        old_text="extension_builder_stub",
        new_text=data.id,
    )
    _rename_files_and_dirs_in_directory(
        directory=extension_dir_path,
        old_text="owner_data",
        new_text=camel_to_snake(data.owner_data.name),
    )


def _replace_text_in_files(
    directory: str,
    old_text: str,
    new_text: str,
    file_extensions: list[str] | None = None,
):
    """
    Recursively replaces text in all files under the given directory.
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
            "editable": data.owner_data.editable,
            "js_fields": [
                field.field_to_js()
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
            "ui_mock_data": [
                json.dumps(
                    {
                        field.name: field.field_mock_value(index=index)
                        for field in data.owner_data.fields + ui_table_columns
                    }
                )
                for index in range(1, 5)
            ],
            "db_fields": [field.field_to_db() for field in data.owner_data.fields],
            "all_fields": [field.field_to_py() for field in data.owner_data.fields],
        },
        "client_data": {
            "name": data.client_data.name,
            "editable": data.client_data.editable,
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
            "ui_mock_data": [
                json.dumps(
                    {
                        field.name: field.field_mock_value(index=index)
                        for field in data.client_data.fields + ui_table_columns
                    }
                )
                for index in range(1, 7)
            ],
            "db_fields": [field.field_to_db() for field in data.client_data.fields],
            "all_fields": [field.field_to_py() for field in data.client_data.fields],
        },
        "settings_data": {
            "enabled": data.settings_data.enabled,
            "is_admin_settings_only": data.settings_data.type == "admin",
            "db_fields": [field.field_to_db() for field in data.settings_data.fields],
            "all_fields": [field.field_to_py() for field in data.settings_data.fields],
        },
        "public_page": data.public_page,
        "cancel_comment": remove_line_marker,
    }


def _fields_to_html_input(
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


def _remove_lines_with_string(file_path: str, target: str) -> None:
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


def _rename_files_and_dirs_in_directory(directory, old_text, new_text):
    """
    Recursively renames files and directories by replacing part of their names.
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


def _is_excluded_dir(path):
    for excluded_dir in excluded_dirs:
        if path.startswith(excluded_dir):
            return True
    return False
