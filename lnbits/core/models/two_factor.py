from pydantic import BaseModel, Field


class TwoFactorConfig(BaseModel):
    """Private persistence model; never embed in Account or User responses."""

    secret: str | None = None
    pending_secret: str | None = None
    pending_until: int = 0
    revision: str = ""
    last_step: int = -1
    recovery_hashes: list[str] = []
    recovery_saved: bool = False
    failures: int = 0
    failure_window: int = 0
    challenges: dict[str, int] = {}


class TwoFactorCode(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class TwoFactorStatus(BaseModel):
    available: bool
    enrolled: bool
    mandatory: bool
    challenge: bool
    recovery_remaining: int
    recovery_saved: bool
