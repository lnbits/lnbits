import pytest

from tests.conftest import pytest_asyncio, settings

from ...helpers import WALLET

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
