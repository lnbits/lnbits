from __future__ import annotations

import inspect
import json
from typing import Any, Optional

from pydantic import BaseModel, BaseSettings, Extra, Field, validator

from lnbits.settings.auth import (
    AuthSettings,
    GitHubAuthSettings,
    GoogleAuthSettings,
    KeycloakAuthSettings,
    NostrAuthSettings,
)
from lnbits.settings.env import EnvSettings
from lnbits.settings.extensions import (
    ExtensionsInstallSettings,
    ExtensionsSettings,
    InstalledExtensionsSettings,
)
from lnbits.settings.fees import FeeSettings
from lnbits.settings.funding_sources import FundingSourcesSettings, LightningSettings
from lnbits.settings.node import NodeUISettings
from lnbits.settings.operations import OpsSettings
from lnbits.settings.persistence import PersistenceSettings
from lnbits.settings.saas import SaaSSettings
from lnbits.settings.security import SecuritySettings
from lnbits.settings.super_user import SuperUserSettings
from lnbits.settings.themes import ThemesSettings
from lnbits.settings.users import UsersSettings
from lnbits.settings.webpush import WebPushSettings


class LNbitsSettings(BaseModel):
    @classmethod
    def validate_list(cls, val):
        if isinstance(val, str):
            val = val.split(",") if val else []
        return val


def list_parse_fallback(v: str):
    v = v.replace(" ", "")
    if len(v) > 0:
        if v.startswith("[") or v.startswith("{"):
            return json.loads(v)
        else:
            return v.split(",")
    else:
        return []


class TransientSettings(InstalledExtensionsSettings):
    # Transient Settings:
    #  - are initialized, updated and used at runtime
    #  - are not read from a file or from the `settings` table
    #  - are not persisted in the `settings` table when the settings are updated
    #  - are cleared on server restart
    first_install: bool = Field(default=False)

    # Indicates that the server should continue to run.
    # When set to false it indicates that the shutdown procedure is ongoing.
    # If false no new tasks, threads, etc should be started.
    # Long running while loops should use this flag instead of `while True:`
    lnbits_running: bool = Field(default=True)

    @classmethod
    def readonly_fields(cls):
        return [f for f in inspect.signature(cls).parameters if not f.startswith("_")]


class EditableSettings(
    UsersSettings,
    ExtensionsSettings,
    ThemesSettings,
    OpsSettings,
    FeeSettings,
    SecuritySettings,
    FundingSourcesSettings,
    LightningSettings,
    WebPushSettings,
    NodeUISettings,
    AuthSettings,
    NostrAuthSettings,
    GoogleAuthSettings,
    GitHubAuthSettings,
    KeycloakAuthSettings,
):
    @validator(
        "lnbits_admin_users",
        "lnbits_allowed_users",
        "lnbits_theme_options",
        "lnbits_admin_extensions",
        pre=True,
    )
    @classmethod
    def validate_editable_settings(cls, val):
        return super().validate_list(val)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            **{k: v for k, v in d.items() if k in inspect.signature(cls).parameters}
        )

    # fixes openapi.json validation, remove field env_names
    class Config:
        @staticmethod
        def schema_extra(schema: dict[str, Any]) -> None:
            for prop in schema.get("properties", {}).values():
                prop.pop("env_names", None)


class UpdateSettings(EditableSettings):
    class Config:
        extra = Extra.forbid


class ReadOnlySettings(
    EnvSettings,
    ExtensionsInstallSettings,
    SaaSSettings,
    PersistenceSettings,
    SuperUserSettings,
):
    lnbits_admin_ui: bool = Field(default=True)

    @validator(
        "lnbits_allowed_funding_sources",
        pre=True,
    )
    @classmethod
    def validate_readonly_settings(cls, val):
        return super().validate_list(val)

    @classmethod
    def readonly_fields(cls):
        return [f for f in inspect.signature(cls).parameters if not f.startswith("_")]


class Settings(EditableSettings, ReadOnlySettings, TransientSettings, BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        json_loads = list_parse_fallback

    def is_user_allowed(self, user_id: str) -> bool:
        return (
            len(self.lnbits_allowed_users) == 0
            or user_id in self.lnbits_allowed_users
            or user_id in self.lnbits_admin_users
            or user_id == self.super_user
        )

    def is_admin_user(self, user_id: str) -> bool:
        return user_id in self.lnbits_admin_users or user_id == self.super_user

    def is_admin_extension(self, ext_id: str) -> bool:
        return ext_id in self.lnbits_admin_extensions

    def is_extension_id(self, ext_id: str) -> bool:
        return ext_id in self.lnbits_all_extensions_ids


class SuperSettings(EditableSettings):
    super_user: str


class AdminSettings(EditableSettings):
    is_super_user: bool
    lnbits_allowed_funding_sources: Optional[list[str]]


def get_funding_source():
    """
    Backwards compatibility
    """
    from lnbits.wallets import get_funding_source

    return get_funding_source()
