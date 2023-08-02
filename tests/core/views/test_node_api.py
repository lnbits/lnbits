import pytest

from lnbits.core import api_payments_create_invoice
from lnbits.nodes.base import NodeChannelsResponse
from tests.conftest import pytest_asyncio, settings

from ...helpers import WALLET, get_random_invoice_data

pytestmark = pytest.mark.skipif(
    WALLET.__node_cls__ is None, reason="Cant test if node implementation isnt avilable"
)


@pytest_asyncio.fixture()
async def node_client(client):
    settings.lnbits_node_ui = True
    settings.lnbits_public_node_ui = False
    yield client
    settings.lnbits_node_ui = False


@pytest_asyncio.fixture()
async def public_node_client(node_client):
    settings.lnbits_public_node_ui = True
    yield node_client
    settings.lnbits_public_node_ui = False


@pytest.mark.asyncio
async def test_node_info_not_found(client, from_super_user):
    response = await client.get("/node/api/v1/info", params={"usr": from_super_user.id})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_node_info_not_found(node_client):
    response = await node_client.get("/node/public/api/v1/info")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_node_info(public_node_client):
    assert settings.lnbits_public_node_ui
    assert settings.lnbits_node_ui
    response = await public_node_client.get("/node/public/api/v1/info")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_node_info(node_client, from_super_user):
    response = await node_client.get(
        "/node/api/v1/info", params={"usr": from_super_user.id}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_node_channels(node_client, from_super_user):
    response = await node_client.get(
        "/node/api/v1/channels", params={"usr": from_super_user.id}
    )
    assert response.status_code == 200
    data = NodeChannelsResponse(**response.json())
    assert len(data.channels)


@pytest.mark.asyncio
async def test_node_peers(node_client, from_super_user):
    response = await node_client.get(
        "/node/api/v1/peers", params={"usr": from_super_user.id}
    )
    assert response.status_code == 200
    assert len(response.json())


@pytest.mark.asyncio
async def test_node_invoices(node_client, from_super_user, invoice):
    response = await node_client.get(
        "/node/api/v1/invoices", params={"usr": from_super_user.id, "limit": 1}
    )
    assert response.status_code == 200
    invoices = response.json()
    assert len(invoices) == 1
    assert invoices[0]["payment_hash"] == invoice["payment_hash"]


@pytest.mark.asyncio
async def test_node_invoices(inkey_headers_from, node_client, from_super_user):
    data = await get_random_invoice_data()
    response = await node_client.post(
        "/api/v1/payments", json=data, headers=inkey_headers_from
    )
    invoice = response.json()

    response = await node_client.get(
        "/node/api/v1/invoices", params={"usr": from_super_user.id, "limit": 1}
    )
    assert response.status_code == 200
    invoices = response.json()["data"]
    assert len(invoices) == 1
    assert invoices[0]["payment_hash"] == invoice["payment_hash"]


@pytest.mark.asyncio
async def test_node_payments(
    node_client, from_super_user, real_invoice, adminkey_headers_from
):
    response = await node_client.post(
        "/api/v1/payments", json=real_invoice, headers=adminkey_headers_from
    )
    assert response.status_code < 300

    response = await node_client.get(
        "/node/api/v1/payments", params={"usr": from_super_user.id, "limit": 1}
    )
    assert response.status_code == 200
    payments = response.json()["data"]
    assert len(payments) == 1
    assert payments[0]["bolt11"] == real_invoice["bolt11"]
