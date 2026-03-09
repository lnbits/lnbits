from uuid import uuid4

import pytest

from lnbits.core.crud import (
    create_account,
    create_admin_settings,
    create_user_extension,
    delete_admin_settings,
    get_account,
    get_super_settings,
    get_user_extensions,
    get_wallets,
)
from lnbits.core.crud.settings import get_settings_field, set_settings_field
from lnbits.core.models import Account
from lnbits.core.models.extensions import UserExtension
from lnbits.core.models.users import RegisterUser
from lnbits.core.services.settings import update_cached_settings
from lnbits.core.services.users import (
    check_admin_settings,
    check_register_activation_settings,
    create_user_account,
    create_user_account_no_ckeck,
    init_admin_settings,
    update_user_account,
    update_user_extensions,
)
from lnbits.settings import Settings


def _pubkey(value: int) -> str:
    return f"{value:064x}"


def _account(
    *,
    id_: str | None = None,
    username: str | None = None,
    email: str | None = None,
    pubkey: str | None = None,
) -> Account:
    account_id = id_ or uuid4().hex
    return Account(
        id=account_id,
        username=username or f"user_{account_id[:8]}",
        email=email or f"{account_id[:8]}@example.com",
        pubkey=pubkey,
    )


@pytest.mark.anyio
async def test_create_user_account_rejects_when_registration_disabled(
    settings: Settings,
):
    settings.lnbits_allow_new_accounts = False

    with pytest.raises(ValueError, match="Account creation is disabled."):
        await create_user_account()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("existing_data", "new_data", "message"),
    [
        (
            {"username": f"user_{uuid4().hex[:8]}"},
            {"username": lambda existing: existing.username},
            "Username already exists.",
        ),
        (
            {"email": f"{uuid4().hex[:8]}@example.com"},
            {"email": lambda existing: existing.email},
            "Email already exists.",
        ),
        (
            {"pubkey": _pubkey(1)},
            {"pubkey": lambda existing: existing.pubkey},
            "Pubkey already exists.",
        ),
    ],
)
async def test_create_user_account_no_check_rejects_duplicate_identity_fields(
    existing_data: dict, new_data: dict, message: str
):
    existing = _account(**existing_data)
    await create_account(existing)

    resolved = {
        key: (value(existing) if callable(value) else value)
        for key, value in new_data.items()
    }
    account = _account(**resolved)

    with pytest.raises(ValueError, match=message):
        await create_user_account_no_ckeck(account)


@pytest.mark.anyio
async def test_create_user_account_no_check_creates_wallet_and_extensions(
    settings: Settings,
):
    account = _account()
    original_default_exts = list(settings.lnbits_user_default_extensions)
    try:
        settings.lnbits_user_default_extensions = ["default-ext"]

        user = await create_user_account_no_ckeck(
            account,
            wallet_name="Primary",
            default_exts=["extra-ext"],
        )
    finally:
        settings.lnbits_user_default_extensions = original_default_exts

    wallets = await get_wallets(user.id)
    user_extensions = await get_user_extensions(user.id)

    assert len(wallets) == 1
    assert wallets[0].name == "Primary"
    assert {ext.extension for ext in user_extensions} == {"default-ext", "extra-ext"}
    assert all(ext.active is True for ext in user_extensions)


@pytest.mark.anyio
async def test_create_user_account_no_check_ignores_duplicate_extension_insert(
    settings: Settings,
):
    account = _account()
    original_default_exts = list(settings.lnbits_user_default_extensions)
    try:
        settings.lnbits_user_default_extensions = ["dup-ext"]

        user = await create_user_account_no_ckeck(account, default_exts=["dup-ext"])
    finally:
        settings.lnbits_user_default_extensions = original_default_exts

    user_extensions = await get_user_extensions(user.id)
    assert [ext.extension for ext in user_extensions] == ["dup-ext"]


@pytest.mark.anyio
async def test_update_user_account_requires_existing_user():
    account = _account()

    with pytest.raises(ValueError, match="User does not exist."):
        await update_user_account(account)


@pytest.mark.anyio
async def test_update_user_account_rejects_conflicting_identity_fields():
    existing = _account(pubkey=_pubkey(2))
    conflict = _account(pubkey=_pubkey(3))
    await create_account(existing)
    await create_account(conflict)

    with pytest.raises(ValueError, match="Username already exists."):
        await update_user_account(
            _account(
                id_=existing.id,
                username=conflict.username,
                email=existing.email,
                pubkey=existing.pubkey,
            )
        )

    with pytest.raises(ValueError, match="Email already exists."):
        await update_user_account(
            _account(
                id_=existing.id,
                username=existing.username,
                email=conflict.email,
                pubkey=existing.pubkey,
            )
        )

    with pytest.raises(ValueError, match="Pubkey already exists."):
        await update_user_account(
            _account(
                id_=existing.id,
                username=existing.username,
                email=existing.email,
                pubkey=conflict.pubkey,
            )
        )


@pytest.mark.anyio
async def test_update_user_account_updates_persisting_password():
    account = _account(pubkey=_pubkey(4))
    account.hash_password("secret1234")
    await create_account(account)

    updated = _account(
        id_=account.id,
        username=f"updated_{account.id[:8]}",
        email=f"{account.id[:8]}+updated@example.com",
        pubkey=(uuid4().hex * 2)[:64],
    )
    result = await update_user_account(updated)
    stored = await get_account(account.id)

    assert result.id == account.id
    assert stored is not None
    assert stored.username == updated.username
    assert stored.email == updated.email
    assert stored.pubkey == updated.pubkey
    assert stored.password_hash == account.password_hash


@pytest.mark.anyio
async def test_update_user_extensions_toggles_existing_and_creates_missing(
    settings: Settings,
):
    original_default_exts = list(settings.lnbits_user_default_extensions)
    try:
        settings.lnbits_user_default_extensions = []
        user = await create_user_account(_account())
    finally:
        settings.lnbits_user_default_extensions = original_default_exts

    await create_user_extension(
        UserExtension(user=user.id, extension="keep", active=True)
    )
    await create_user_extension(
        UserExtension(user=user.id, extension="enable", active=False)
    )
    await create_user_extension(
        UserExtension(user=user.id, extension="disable", active=True)
    )

    await update_user_extensions(user.id, ["keep", "enable", "new-ext"])

    user_extensions = {
        ext.extension: ext.active for ext in await get_user_extensions(user.id)
    }
    assert user_extensions == {
        "keep": True,
        "enable": True,
        "disable": False,
        "new-ext": True,
    }


@pytest.mark.anyio
async def test_check_admin_settings_initializes_cache_and_marks_first_install(
    settings: Settings, tmp_path
):
    previous_settings = await get_super_settings()
    previous_super_user = settings.super_user
    previous_data_folder = settings.lnbits_data_folder
    previous_admin_ui = settings.lnbits_admin_ui
    previous_first_install = settings.first_install
    super_user = uuid4().hex

    try:
        await delete_admin_settings()
        settings.super_user = super_user
        settings.lnbits_data_folder = str(tmp_path)
        settings.lnbits_admin_ui = True
        settings.first_install = False

        await check_admin_settings()

        stored_settings = await get_super_settings()
        stored_account = await get_account(super_user)
        assert stored_settings is not None
        assert stored_settings.super_user == super_user
        assert stored_account is not None
        assert stored_account.extra.provider == "env"
        assert settings.first_install is True
        assert (tmp_path / ".super_user").read_text() == super_user
    finally:
        await delete_admin_settings()
        if previous_settings:
            await create_admin_settings(
                previous_settings.super_user,
                previous_settings.dict(exclude={"super_user"}),
            )
            update_cached_settings(previous_settings.dict())
        settings.super_user = previous_super_user
        settings.lnbits_data_folder = previous_data_folder
        settings.lnbits_admin_ui = previous_admin_ui
        settings.first_install = previous_first_install


@pytest.mark.anyio
async def test_init_admin_settings_creates_account_and_wallet_when_missing():
    super_user = uuid4().hex

    result = await init_admin_settings(super_user)

    wallets = await get_wallets(super_user)
    assert result.super_user == super_user
    assert await get_account(super_user) is not None
    assert len(wallets) == 1


@pytest.mark.anyio
async def test_check_register_activation_settings_handles_invitation_codes(
    settings: Settings,
):
    reusable = "reusable-code"
    one_time = "one-time-code"
    original_require_activation = settings.lnbits_require_user_activation
    original_by_invite = settings.lnbits_user_activation_by_invitation_code
    original_reusable = settings.lnbits_register_reusable_activation_code
    original_one_time = list(settings.lnbits_register_one_time_activation_codes)
    previous_stored_codes = await get_settings_field(
        "lnbits_register_one_time_activation_codes"
    )

    try:
        settings.lnbits_require_user_activation = False
        assert (
            await check_register_activation_settings(
                RegisterUser(
                    username=f"user_{uuid4().hex[:8]}",
                    password="secret1234",
                    password_repeat="secret1234",
                )
            )
            is None
        )

        settings.lnbits_require_user_activation = True
        settings.lnbits_user_activation_by_invitation_code = True
        settings.lnbits_register_reusable_activation_code = reusable
        settings.lnbits_register_one_time_activation_codes = [one_time]

        with pytest.raises(ValueError, match="Invitation code cannot be empty."):
            await check_register_activation_settings(
                RegisterUser(
                    username=f"user_{uuid4().hex[:8]}",
                    password="secret1234",
                    password_repeat="secret1234",
                    invitation_code=" ",
                )
            )

        assert (
            await check_register_activation_settings(
                RegisterUser(
                    username=f"user_{uuid4().hex[:8]}",
                    password="secret1234",
                    password_repeat="secret1234",
                    invitation_code=reusable,
                )
            )
            is None
        )

        assert (
            await check_register_activation_settings(
                RegisterUser(
                    username=f"user_{uuid4().hex[:8]}",
                    password="secret1234",
                    password_repeat="secret1234",
                    invitation_code=one_time,
                )
            )
            is None
        )
        assert one_time not in settings.lnbits_register_one_time_activation_codes
        stored_codes = await get_settings_field(
            "lnbits_register_one_time_activation_codes"
        )
        assert stored_codes is not None
        assert stored_codes.value == []

        with pytest.raises(ValueError, match="Invalid invitation code."):
            await check_register_activation_settings(
                RegisterUser(
                    username=f"user_{uuid4().hex[:8]}",
                    password="secret1234",
                    password_repeat="secret1234",
                    invitation_code="bad-code",
                )
            )

        settings.lnbits_user_activation_by_invitation_code = False
        with pytest.raises(ValueError, match="No activation method provided."):
            await check_register_activation_settings(
                RegisterUser(
                    username=f"user_{uuid4().hex[:8]}",
                    password="secret1234",
                    password_repeat="secret1234",
                    invitation_code=reusable,
                )
            )
    finally:
        settings.lnbits_require_user_activation = original_require_activation
        settings.lnbits_user_activation_by_invitation_code = original_by_invite
        settings.lnbits_register_reusable_activation_code = original_reusable
        settings.lnbits_register_one_time_activation_codes = original_one_time
        await set_settings_field(
            "lnbits_register_one_time_activation_codes",
            previous_stored_codes.value if previous_stored_codes else original_one_time,
        )
