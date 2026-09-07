import httpx
import pytest

from lnbits.core.views import node_api
from lnbits.nodes.phoenixd import PhoenixdNode
from lnbits.wallets.phoenixd import PhoenixdWallet


@pytest.fixture
async def phoenixd_node(mocker, settings):
    settings.lnbits_node_ui = True
    wallet = object.__new__(PhoenixdWallet)
    wallet.client = httpx.AsyncClient(base_url="http://phoenixd.test")
    mocker.patch.object(
        wallet.client,
        "request",
        side_effect=AssertionError("Unexpected daemon request"),
    )
    mocker.patch.object(node_api, "get_funding_source", return_value=wallet)
    node = PhoenixdNode(wallet)
    yield node
    await wallet.client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "operation,data",
    [
        (
            "close",
            {
                "channel_id": "ab" * 32,
                "address": "bc1destinationaddress",
                "fee_rate": 3,
            },
        ),
        (
            "send",
            {"amount_sat": 1000, "address": "bc1destinationaddress", "fee_rate": 3},
        ),
        ("bump", {"fee_rate": 3}),
        ("export", {}),
    ],
)
async def test_phoenixd_actions_require_superuser(
    client, admin_user, phoenixd_node, operation, data
):
    response = await client.post(f"/node/api/v1/phoenixd/{operation}", json=data)
    assert response.status_code in (401, 403)
    login = await client.post(
        "/api/v1/auth", json={"username": admin_user.username, "password": "secret1234"}
    )
    token = login.json()["access_token"]
    client.cookies.clear()
    response = await client.post(
        f"/node/api/v1/phoenixd/{operation}",
        json=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_phoenixd_close_validation_and_form_mapping(
    client, superuser_token, phoenixd_node, mocker
):
    transact = mocker.patch.object(PhoenixdNode, "transact", return_value="cd" * 32)
    headers = {"Authorization": f"Bearer {superuser_token}"}
    data = {"channel_id": "ab" * 32, "address": "bc1destinationaddress", "fee_rate": 5}
    response = await client.post(
        "/node/api/v1/phoenixd/close", json=data, headers=headers
    )
    assert response.status_code == 200
    assert response.json() == {"txid": "cd" * 32}
    transact.assert_awaited_once_with(
        "close",
        {
            "channelId": "ab" * 32,
            "address": "bc1destinationaddress",
            "feerateSatByte": 5,
        },
    )
    transact.reset_mock()
    for changes in (
        {"channel_id": "invalid"},
        {"fee_rate": 0},
        {"fee_rate": 1.5},
        {"fee_rate": True},
        {"address": ""},
    ):
        response = await client.post(
            "/node/api/v1/phoenixd/close", json={**data, **changes}, headers=headers
        )
        assert response.status_code == 400
    transact.assert_not_awaited()


@pytest.mark.anyio
async def test_phoenixd_send_bump_and_export(
    client, superuser_token, phoenixd_node, mocker, settings
):
    transact = mocker.patch.object(PhoenixdNode, "transact", return_value="cd" * 32)
    export = mocker.patch.object(PhoenixdNode, "export_history")
    headers = {"Authorization": f"Bearer {superuser_token}"}
    response = await client.post(
        "/node/api/v1/phoenixd/send",
        json={"amount_sat": 10, "address": "bc1destinationaddress", "fee_rate": 2},
        headers=headers,
    )
    assert response.status_code == 200
    transact.assert_awaited_with(
        "send",
        {"amountSat": 10, "address": "bc1destinationaddress", "feerateSatByte": 2},
    )
    response = await client.post(
        "/node/api/v1/phoenixd/bump", json={"fee_rate": 4}, headers=headers
    )
    assert response.status_code == 200
    transact.assert_awaited_with("bump", {"feerateSatByte": 4})
    settings.lnbits_node_ui_transactions = False
    response = await client.post("/node/api/v1/phoenixd/export", headers=headers)
    assert response.status_code == 503
    export.assert_not_awaited()
    settings.lnbits_node_ui_transactions = True
    response = await client.post("/node/api/v1/phoenixd/export", headers=headers)
    assert response.status_code == 200
    export.assert_awaited_once()


@pytest.mark.anyio
async def test_phoenixd_rank_stays_private_and_node_ui_guard(
    client, superuser_token, phoenixd_node, settings
):
    headers = {"Authorization": f"Bearer {superuser_token}"}
    response = await client.get("/node/api/v1/rank", headers=headers)
    assert response.status_code == 200
    assert response.json() is None
    settings.lnbits_node_ui = False
    response = await client.post(
        "/node/api/v1/phoenixd/bump", json={"fee_rate": 1}, headers=headers
    )
    assert response.status_code == 503
