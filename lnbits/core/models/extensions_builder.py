from __future__ import annotations

import json

from pydantic import BaseModel, validator

from lnbits.helpers import camel_to_snake, is_camel_case, is_snake_case


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

    @validator("name")
    def validate_name(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Owner Data name is required.")
        if not is_snake_case(v):
            raise ValueError(f"Field Name must be snake_case. Found: {v}")
        return v

    @validator("type")
    def validate_type(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Owner Data type is required")
        if v not in [
            "str",
            "int",
            "float",
            "bool",
            "datetime",
            "json",
            "wallet",
            "currency",
            "text",
        ]:
            raise ValueError(
                "Field Type must be one of: "
                "str, int, float, bool, datetime, json, wallet, currency, text."
                f" Found: {v}"
            )
        return v


class DataFields(BaseModel):
    name: str
    fields: list[DataField] = []

    @validator("name")
    def validate_name(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Data fields name is required")
        if not is_camel_case(v):
            raise ValueError(f"Data name must be CamelCase. Found: {v}")
        return v


class SettingsFields(DataFields):
    enabled: bool = False
    type: str = "user"

    @validator("type")
    def validate_type(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Settings type is required")
        if v not in ["user", "admin"]:
            raise ValueError("Field Type must be one of: user, admin." f" Found: {v}")
        return v


class ActionFields(BaseModel):
    generate_action: bool = False
    generate_payment_logic: bool = False
    wallet_id: str | None = None
    currency: str | None = None
    amount: str | None = None
    paid_flag: str | None = None


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

    def normalize(self) -> None:
        self.name = self.name.strip()
        self.stub_version = self.stub_version.strip()
        if self.short_description:
            self.short_description = self.short_description.strip()
        if self.description:
            self.description = self.description.strip()
        if not self.public_page.has_public_page:
            self.public_page.action_fields.generate_action = False
            self.public_page.action_fields.generate_payment_logic = False
        if not self.public_page.action_fields.generate_action:
            self.public_page.action_fields.generate_payment_logic = False

    @validator("id")
    def validate_id(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Extension ID is required")
        if not is_snake_case(v):
            raise ValueError(f"Extension Id must be snake_case. Found: {v}")
        return v

    @validator("name")
    def validate_name(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Extension name is required")
        return v

    @validator("stub_version")
    def validate_stub_version(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Extension stub version is required")

        return v

    @validator("owner_data")
    def validate_owner_data(cls, v: DataFields) -> DataFields:
        if len(v.fields) == 0:
            raise ValueError("At least one owner data field is required")
        return v

    @validator("client_data")
    def validate_client_data(cls, v: DataFields) -> DataFields:
        if len(v.fields) == 0:
            raise ValueError("At least one client data field is required")
        return v
