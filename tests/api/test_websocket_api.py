from unittest.mock import AsyncMock

from pytest_mock.plugin import MockerFixture


def test_websocket_api_connects_and_updates(test_client):
    with test_client.websocket_connect("/api/v1/ws/demo-item") as websocket:
        response = test_client.post("/api/v1/ws/demo-item", params={"data": "hello"})
        assert response.status_code == 200
        assert response.json() == {"sent": True, "data": "hello"}
        assert websocket.receive_text() == "hello"

        response = test_client.get("/api/v1/ws/demo-item/world")
        assert response.status_code == 200
        assert response.json() == {"sent": True, "data": "world"}
        assert websocket.receive_text() == "world"


def test_websocket_api_reports_send_failures(test_client, mocker: MockerFixture):
    mocker.patch(
        "lnbits.core.views.websocket_api.websocket_manager.send",
        AsyncMock(side_effect=RuntimeError("boom")),
    )

    post_response = test_client.post("/api/v1/ws/demo-item", params={"data": "oops"})
    assert post_response.status_code == 200
    assert post_response.json() == {"sent": False, "data": "oops"}

    get_response = test_client.get("/api/v1/ws/demo-item/oops")
    assert get_response.status_code == 200
    assert get_response.json() == {"sent": False, "data": "oops"}
