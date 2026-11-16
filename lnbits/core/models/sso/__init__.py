"""SSO authentication providers for LNbits."""

from fastapi_sso.sso.base import OpenID


class VerifiedOpenID(OpenID):
    email_verified: bool = False
