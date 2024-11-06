from __future__ import annotations

from pydantic import Field

from .lnbits import LNbitsSettings


class UsersSettings(LNbitsSettings):
    lnbits_admin_users: list[str] = Field(default=[])
    lnbits_allowed_users: list[str] = Field(default=[])
    lnbits_allow_new_accounts: bool = Field(default=True)

    @property
    def new_accounts_allowed(self) -> bool:
        return self.lnbits_allow_new_accounts and len(self.lnbits_allowed_users) == 0
