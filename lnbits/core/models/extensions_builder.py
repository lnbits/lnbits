from __future__ import annotations

import json

from pydantic import BaseModel

from lnbits.helpers import camel_to_snake


class DataField(BaseModel):
    name: str
    type: str
    label: str | None = None
    hint: str | None = None
    optional: bool = False
    editable: bool = False
    searchable: bool = False
    sortable: bool = False
    fields: list[DataField] = []

    def field_to_py(self) -> str:
        field_name = camel_to_snake(self.name)
        field_type = self.type
        if field_type == "json":
            field_type = "dict"
        elif field_type in ["wallet", "currency", "text"]:
            field_type = "str"
        if self.optional:
            field_type += " | None"
        return f"{field_name}: {field_type}"

    def field_to_ui_table_column(self) -> str:
        column = {
            "name": self.name,
            "align": "left",
            "label": self.label or self.name,
            "field": self.name,
            "sortable": self.sortable,
        }

        return json.dumps(column)

    def field_to_db(self) -> str:
        field_name = camel_to_snake(self.name)
        field_type = self.type
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
        if not self.optional:
            db_field += " NOT NULL"
        if field_type == "json":
            db_field += " DEFAULT '{empty_dict}'"
        return db_field


class DataFields(BaseModel):
    name: str
    fields: list[DataField] = []


class SettingsFields(DataFields):
    enabled: bool = False
    type: str = "user"  # "user" or "admin"


class ActionFields(BaseModel):
    generate_action: bool = False
    wallet_id: str | None = None
    currency: str | None = None
    amount: str | None = None


class OwnerDataFields(BaseModel):
    name: str | None = None
    description: str | None = None


class ClientDataFields(BaseModel):
    public_inputs: list[str] = []


class PublicPageFields(BaseModel):
    has_public_page: bool = False
    owner_data_fields: OwnerDataFields
    client_data_fields: ClientDataFields
    action_fields: ActionFields


class ExtensionData(BaseModel):
    id: str
    name: str
    stub_version: str
    short_description: str | None = None
    description: str | None = None
    owner_data: DataFields
    client_data: DataFields
    settings_data: SettingsFields
    public_page: PublicPageFields
