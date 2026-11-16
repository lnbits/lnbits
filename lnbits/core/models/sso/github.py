import httpx
from fastapi_sso.sso.base import SSOLoginError
from fastapi_sso.sso.github import GithubSSO as BaseGithubSSO

from . import VerifiedOpenID


class GithubSSO(BaseGithubSSO):
    async def openid_from_response(
        self, response: dict, session: httpx.AsyncClient | None = None
    ) -> VerifiedOpenID:
        if session is None:
            raise SSOLoginError(401, "Cannot verify the SSO email.")
        emails_response = await session.get(self.emails_endpoint)
        emails_response.raise_for_status()
        email = next(
            (
                item.get("email")
                for item in emails_response.json()
                if item.get("primary") is True and item.get("verified") is True
            ),
            None,
        )
        if not email:
            raise SSOLoginError(401, "A verified primary email is required for SSO.")
        identity = await super().openid_from_response(
            {**response, "email": email}, session
        )
        return VerifiedOpenID(**identity.model_dump(), email_verified=True)
