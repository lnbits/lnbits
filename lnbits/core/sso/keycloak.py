"""Keycloak SSO Login Helper
"""

from typing import Optional

import httpx
from fastapi_sso.sso.base import DiscoveryDocument, OpenID, SSOBase


class KeycloakSSO(SSOBase):
    """Class providing login via Keycloak OAuth"""

    provider = "keycloak"
    scope = ["openid", "email", "profile"]
    discovery_url = ""

    async def openid_from_response(
        self, response: dict, session: Optional["httpx.AsyncClient"] = None
    ) -> OpenID:
        """Return OpenID from user information provided by Keycloak"""
        return OpenID(
            email=response.get("email", ""),
            provider=self.provider,
            id=response.get("sub"),
            first_name=response.get("given_name"),
            last_name=response.get("family_name"),
            display_name=response.get("name"),
            picture=response.get("picture"),
        )

    async def get_discovery_document(self) -> DiscoveryDocument:
        """Get document containing handy urls"""
        async with httpx.AsyncClient() as session:
            response = await session.get(self.discovery_url)
            content = response.json()

            return content
