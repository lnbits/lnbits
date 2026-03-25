import pytest
from pydantic import ValidationError

from lnbits.core.models.extensions import InstallableExtension
from lnbits.core.models.lnurl import StoredPayLink
from lnbits.core.models.users import UserLabel
from lnbits.core.models.wallets import (
    Wallet,
    WalletPermission,
    WalletSharePermission,
    WalletShareStatus,
)
from lnbits.db import dict_to_model


def test_user_label_uses_pydantic_v2_pattern_validation():
    label = UserLabel(name="label-1", color="#FF00AA")

    assert label.name == "label-1"
    assert label.color == "#FF00AA"

    with pytest.raises(ValidationError):
        UserLabel(name="label-1", color="bad-color")


def test_wallet_has_stored_paylinks_field_and_mirrors_it():
    source_wallet = Wallet(
        id="source-wallet-id",
        user="source-user-id",
        name="source",
        adminkey="admin-key",
        inkey="invoice-key",
    )
    source_wallet.stored_paylinks.links.append(
        StoredPayLink(lnurl="lnurl1example", label="saved paylink")
    )

    shared_wallet = Wallet(
        id="shared-wallet-id",
        user="shared-user-id",
        name="shared",
        adminkey="shared-admin-key",
        inkey="shared-invoice-key",
    )
    source_wallet.extra.shared_with.append(
        WalletSharePermission(
            request_id="share-request-id",
            username="shared-user",
            shared_with_wallet_id=shared_wallet.id,
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.APPROVED,
        )
    )
    shared_wallet.mirror_shared_wallet(source_wallet)

    assert shared_wallet.stored_paylinks.links[0].lnurl == "lnurl1example"
    assert shared_wallet.stored_paylinks.links[0].label == "saved paylink"


def test_db_dict_to_model_parses_optional_nested_pydantic_v2_models():
    ext = dict_to_model(
        {
            "id": "ext-id",
            "name": "Extension",
            "version": "1.0.0",
            "active": 1,
            "meta": (
                '{"installed_release": {"name": "Release", "version": "1.0.0", '
                '"archive": "https://example.com/release.zip", '
                '"source_repo": "lnbits/example"}, "payments": [], '
                '"dependencies": [], "featured": false, '
                '"has_paid_release": false, "has_free_release": false}'
            ),
        },
        InstallableExtension,
    )

    assert ext.meta is not None
    assert ext.meta.installed_release is not None
    assert ext.meta.installed_release.source_repo == "lnbits/example"
