from __future__ import annotations

from enum import Enum

from pydantic import Field

from .lnbits import LNbitsSettings


class AuthMethods(Enum):
    user_id_only = "user-id-only"
    username_and_password = "username-password"
    nostr_auth_nip98 = "nostr-auth-nip98"
    google_auth = "google-auth"
    github_auth = "github-auth"
    keycloak_auth = "keycloak-auth"

    @classmethod
    def all(cls):
        return [
            AuthMethods.user_id_only.value,
            AuthMethods.username_and_password.value,
            AuthMethods.nostr_auth_nip98.value,
            AuthMethods.google_auth.value,
            AuthMethods.github_auth.value,
            AuthMethods.keycloak_auth.value,
        ]


class AuthSettings(LNbitsSettings):
    auth_token_expire_minutes: int = Field(default=525600)
    auth_all_methods = [a.value for a in AuthMethods]
    auth_allowed_methods: list[str] = Field(
        default=[
            AuthMethods.user_id_only.value,
            AuthMethods.username_and_password.value,
        ]
    )
    # How many seconds after login the user is allowed to update its credentials.
    # A fresh login is required afterwards.
    auth_credetials_update_threshold: int = Field(default=120)

    def is_auth_method_allowed(self, method: AuthMethods):
        return method.value in self.auth_allowed_methods


class NostrAuthSettings(LNbitsSettings):
    nostr_absolute_request_urls: list[str] = Field(
        default=["http://127.0.0.1:5000", "http://localhost:5000"]
    )


class GoogleAuthSettings(LNbitsSettings):
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")


class GitHubAuthSettings(LNbitsSettings):
    github_client_id: str = Field(default="")
    github_client_secret: str = Field(default="")


class KeycloakAuthSettings(LNbitsSettings):
    keycloak_discovery_url: str = Field(default="")
    keycloak_client_id: str = Field(default="")
    keycloak_client_secret: str = Field(default="")
