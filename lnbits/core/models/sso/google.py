import httpx
from fastapi_sso.sso.base import SSOLoginError
from fastapi_sso.sso.google import GoogleSSO as BaseGoogleSSO

from . import VerifiedOpenID


class GoogleSSO(BaseGoogleSSO):
    async def openid_from_response(
        self, response: dict, session: httpx.AsyncClient | None = None
    ) -> VerifiedOpenID:
        if response.get("email_verified") is not True:
            raise SSOLoginError(401, "A verified email is required for SSO.")
        identity = await super().openid_from_response(response, session)
        return VerifiedOpenID(**identity.model_dump(), email_verified=True)
