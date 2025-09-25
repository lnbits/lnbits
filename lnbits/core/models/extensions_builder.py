from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, validator

from lnbits.helpers import (
    camel_to_snake,
    is_camel_case,
    is_snake_case,
    urlsafe_short_hash,
)


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

    def normalize(self) -> None:
        self.name = self.name.strip()
        self.type = self.type.strip()
        if self.label:
            self.label = self.label.strip()
        if self.hint:
            self.hint = self.hint.strip()
        if self.type == "json":
            self.editable = False
            self.searchable = False
            self.sortable = False
        else:
            self.fields = []

        for field in self.fields:
            field.normalize()

    def field_to_py(self) -> str:
        field_name = camel_to_snake(self.name)
        field_type = self.type
        if self.type == "json":
            field_type = "dict"
        elif self.type in ["wallet", "currency", "text"]:
            field_type = "str"
        if self.optional:
            field_type += " | None"
        if self.type == "currency":
            field_type += ' = "sat"'
        return f"{field_name}: {field_type}"

    def field_to_js(self) -> str:
        field_name = camel_to_snake(self.name)
        default_value = "null"
        if self.type == "json":
            default_value = "{}"
        if self.type == "currency":
            default_value = '"sat"'
        return f"{field_name}: {default_value}"

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

    def field_mock_value(self, index: int) -> Any:
        if self.name == "id":
            return urlsafe_short_hash()
        if self.type == "int":
            return index
        elif self.type == "float":
            return float(f"{index}.0{index * 2}")
        elif self.type == "bool":
            return True if index % 2 == 0 else False
        elif self.type == "datetime":
            return (datetime.now(timezone.utc) - timedelta(hours=index * 2)).isoformat()
        elif self.type == "json":
            return {"key": "value"}
        elif self.type == "currency":
            return "USD"
        else:
            return f"{self.name} {index}"

    @validator("name")
    def validate_name(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Field name is required.")
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

    @validator("label")
    def validate_label(cls, v: str | None) -> str | None:
        if v and '"' in v:
            raise ValueError(
                f'Field label cannot contain double quotes ("). Value: {v}'
            )
        return v

    @validator("hint")
    def validate_hint(cls, v: str | None) -> str | None:
        if v and '"' in v:
            raise ValueError(f'Field hint cannot contain double quotes ("). Value: {v}')
        return v


class DataFields(BaseModel):
    name: str
    editable: bool = True
    fields: list[DataField] = []

    def __init__(self, **data):
        super().__init__(**data)
        self.normalize()

    def normalize(self) -> None:
        self.name = self.name.strip()
        for field in self.fields:
            field.normalize()
        if all(not field.editable for field in self.fields):
            self.editable = False

    def get_field_by_name(self, name: str | None) -> DataField | None:
        if not name:
            return None
        for field in self.fields:
            if field.name == name:
                return field
        return None

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
    amount_source: Literal["owner_data", "client_data"] | None = None
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


class PreviewAction(BaseModel):
    is_preview_mode: bool = False
    is_settings_preview: bool = False
    is_owner_data_preview: bool = False
    is_client_data_preview: bool = False
    is_public_page_preview: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        if not self.is_preview_mode:
            self.is_settings_preview = False
            self.is_owner_data_preview = False
            self.is_client_data_preview = False
            self.is_public_page_preview = False


class ExtensionData(BaseModel):
    id: str
    name: str
    stub_version: str | None
    short_description: str | None = None
    description: str | None = None
    owner_data: DataFields
    client_data: DataFields
    settings_data: SettingsFields
    public_page: PublicPageFields
    preview_action: PreviewAction = PreviewAction()

    def __init__(self, **data):
        super().__init__(**data)
        self.validate_data()
        self.normalize()

    def normalize(self) -> None:
        self.id = self.id.strip()
        self.name = self.name.strip()
        if self.stub_version:
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

    def validate_data(self) -> None:
        self._validate_field_names()
        self._validate_public_page_fields()
        self._validate_action_fields()

    def _validate_public_page_fields(self) -> None:
        if not self.public_page.has_public_page:
            return

        public_page_name = self.public_page.owner_data_fields.name
        if public_page_name:
            public_page_name_field = self.owner_data.get_field_by_name(public_page_name)
            if not public_page_name_field:
                raise ValueError(
                    "Public Page Name must be one of the owner data fields."
                    f" Received: {public_page_name}."
                )

        public_page_description = self.public_page.owner_data_fields.description
        if public_page_description:
            public_page_description_field = self.owner_data.get_field_by_name(
                public_page_description
            )
            if not public_page_description_field:
                raise ValueError(
                    "Public Page Description must be one of the owner data fields."
                    f" Received: {public_page_description}."
                )

        public_page_inputs = self.public_page.client_data_fields.public_inputs
        if public_page_inputs:
            for input_field in public_page_inputs:
                input_field_obj = self.client_data.get_field_by_name(input_field)
                if not input_field_obj:
                    raise ValueError(
                        "Public Page Input fields"
                        " must be one of the client data fields."
                        f" Received: {input_field}."
                    )

    def _validate_action_fields(self) -> None:
        if not self.public_page.action_fields.generate_action:
            return
        if not self.public_page.action_fields.generate_payment_logic:
            return

        self._validate_owner_data_fields()
        self._validate_client_data_fields()

    def _validate_owner_data_fields(self) -> None:
        wallet_id = self.public_page.action_fields.wallet_id
        if wallet_id:
            wallet_id_field = self.owner_data.get_field_by_name(wallet_id)
            if not wallet_id_field:
                raise ValueError(
                    "Action Wallet ID must be one of the owner data fields."
                    f" Received: {wallet_id}."
                )
            if wallet_id_field.type != "wallet":
                raise ValueError(
                    "Action Wallet ID field type must be 'wallet'."
                    f" Received: {wallet_id_field.type}."
                )
        currency = self.public_page.action_fields.currency
        if currency:
            currency_field = self.owner_data.get_field_by_name(currency)
            if not currency_field:
                raise ValueError(
                    "Action Currency must be one of the owner data fields."
                    f" Received: {currency}."
                )
            if currency_field.type != "currency":
                raise ValueError(
                    "Action Currency field type must be 'currency'."
                    f" Received: {currency_field.type}."
                )

    def _validate_field_names(self) -> None:
        reserved_names = {"id", "created_at", "updated_at"}
        nok = {f.name for f in self.owner_data.fields}.intersection(reserved_names)
        if nok:
            raise ValueError(
                f"Owner Data fields cannot have reserved names: '{', '.join(nok)}.'"
            )
        nok = {f.name for f in self.client_data.fields}.intersection(reserved_names)
        if nok:
            raise ValueError(
                f"Client Data fields cannot have reserved names: '{', '.join(nok)}.'"
            )
        nok = {f.name for f in self.settings_data.fields}.intersection(reserved_names)
        if nok:
            raise ValueError(
                f"Settings fields cannot have reserved names: '{', '.join(nok)}.'"
            )

    def _validate_client_data_fields(self) -> None:
        amount = self.public_page.action_fields.amount
        amount_source = self.public_page.action_fields.amount_source
        if amount_source and amount:
            if amount_source == "owner_data":
                amount_field = self.owner_data.get_field_by_name(amount)
            else:
                amount_field = self.client_data.get_field_by_name(amount)
            if not amount_field:
                raise ValueError(
                    "Action Amount must be one of the "
                    "client data or owner data fields."
                    f" Received: {amount}."
                )
            if amount_field.type not in ["int", "float"]:
                raise ValueError(
                    "Action Amount field type must be 'int' or 'float'."
                    f" Received: {amount_field.type}."
                )
        paid_flag = self.public_page.action_fields.paid_flag
        if paid_flag:
            paid_flag_field = self.client_data.get_field_by_name(paid_flag)
            if not paid_flag_field:
                raise ValueError(
                    "Action Paid Flag must be one of the client data fields."
                    f" Received: {paid_flag}."
                )
            if paid_flag_field.type != "bool":
                raise ValueError(
                    "Action Paid Flag field type must be 'bool'."
                    f" Received: {paid_flag_field.type}."
                )

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
    def validate_stub_version(cls, v: str | None) -> str | None:
        if v and '"' in v:
            raise ValueError(
                f'Extension stub version cannot contain double quotes ("). Value: {v}'
            )
        return v

    @validator("short_description")
    def validate_short_description(cls, v: str | None) -> str | None:
        if v and '"' in v:
            raise ValueError(
                f'Field short description cannot contain double quotes ("). Value: {v}'
            )
        return v

    @validator("description")
    def validate_description(cls, v: str | None) -> str | None:
        if v and '"' in v:
            raise ValueError(
                f'Field description cannot contain double quotes ("). Value: {v}'
            )
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
