import pytest

from lnbits.core.services import websocket_manager, websocket_updater


@pytest.mark.anyio
async def test_websocket_api_receives_only_server_updates(test_client):
    with test_client.websocket_connect("/api/v1/ws/demo-item") as websocket:
        response = test_client.post("/api/v1/ws/demo-item", params={"data": "post"})
        assert response.status_code == 404

        response = test_client.get("/api/v1/ws/demo-item/get")
        assert response.status_code == 404

        websocket.portal.call(websocket_manager.send, "demo-item", "hello")
        assert websocket.receive_text() == "hello"

        websocket.portal.call(websocket_updater, "demo-item", "world")
        assert websocket.receive_text() == "world"
