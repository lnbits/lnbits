from __future__ import annotations

from pydantic import BaseModel


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
