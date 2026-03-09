from collections.abc import Callable
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from pytest_mock.plugin import MockerFixture

from lnbits.core.views import node_api
from lnbits.db import Filters, Page
from lnbits.nodes.base import (
    ChannelBalance,
    ChannelPoint,
    ChannelState,
    ChannelStats,
    Node,
    NodeChannel,
    NodeFees,
    NodeInfoResponse,
    NodeInvoice,
    NodePayment,
    NodePeerInfo,
    PublicNodeInfo,
)
from lnbits.settings import Settings
from lnbits.wallets.base import Feature


class FakeNode:
    def __init__(self):
        self.channel = NodeChannel(
            id="chan-1",
            short_id="123x1x0",
            peer_id="peer-1",
            name="Peer One",
            color="#ffffff",
            state=ChannelState.ACTIVE,
            balance=ChannelBalance(local_msat=1000, remote_msat=2000, total_msat=3000),
            point=ChannelPoint(funding_txid="ab" * 32, output_index=1),
            fee_ppm=10,
            fee_base_msat=1000,
        )
        self.peer = NodePeerInfo(id="peer-1", alias="Peer One", addresses=["127.0.0.1"])
        self.info = NodeInfoResponse(
            id="node-id",
            backend_name="FakeNode",
            alias="Fake Alias",
            color="#ffffff",
            num_peers=1,
            blockheight=1,
            channel_stats=ChannelStats(
                counts={ChannelState.ACTIVE: 1},
                avg_size=3000,
                biggest_size=3000,
                smallest_size=3000,
                total_capacity=3000,
            ),
            addresses=["127.0.0.1:9735"],
            onchain_balance_sat=1,
            onchain_confirmed_sat=1,
            fees=NodeFees(total_msat=0),
            balance_msat=3000,
        )
        self.fees_updated: tuple[str, int | None, int | None] | None = None

    async def get_public_info(self) -> PublicNodeInfo:
        return PublicNodeInfo(**self.info.dict())

    async def get_info(self) -> NodeInfoResponse:
        return self.info

    async def get_channels(self) -> list[NodeChannel]:
        return [self.channel]

    async def get_channel(self, channel_id: str) -> NodeChannel | None:
        return self.channel if channel_id == self.channel.id else None

    async def open_channel(
        self,
        peer_id: str,
        funding_amount: int,
        push_amount: int | None = None,
        fee_rate: int | None = None,
    ) -> ChannelPoint:
        assert peer_id == "peer-1"
        assert funding_amount == 10_000
        assert push_amount == 100
        assert fee_rate == 5
        return ChannelPoint(funding_txid="cd" * 32, output_index=0)

    async def close_channel(
        self,
        short_id: str | None = None,
        point: ChannelPoint | None = None,
        force: bool = False,
    ) -> list[NodeChannel]:
        assert short_id == self.channel.short_id
        assert point is None
        assert force is True
        return [self.channel]

    async def set_channel_fee(
        self, channel_id: str, fee_base_msat: int | None, fee_ppm: int | None
    ) -> None:
        self.fees_updated = (channel_id, fee_base_msat, fee_ppm)

    async def get_payments(self, filters: Filters[Any]) -> Page[NodePayment]:
        return Page(
            data=[
                NodePayment(
                    pending=False,
                    amount=1,
                    fee=0,
                    memo="payment",
                    time=1,
                    preimage="11" * 32,
                    payment_hash="22" * 32,
                )
            ],
            total=1,
        )

    async def get_invoices(self, filters: Filters[Any]) -> Page[NodeInvoice]:
        return Page(
            data=[
                NodeInvoice(
                    pending=False,
                    amount=1,
                    memo="invoice",
                    bolt11="lnbc1dummy",
                    preimage="11" * 32,
                    payment_hash="33" * 32,
                )
            ],
            total=1,
        )

    async def get_peers(self) -> list[NodePeerInfo]:
        return [self.peer]

    async def connect_peer(self, uri: str) -> dict[str, str]:
        return {"uri": uri}

    async def disconnect_peer(self, peer_id: str) -> dict[str, str]:
        return {"peer_id": peer_id}

    async def get_id(self) -> str:
        return "fake-node-id"


class FakeFundingSource:
    def __init__(
        self,
        features: list[Feature],
        node_factory: Callable[[Any], Any] | None,
    ):
        self.features = features
        self.__node_cls__ = node_factory


class MockHTTPResponse:
    def __init__(
        self, json_data: dict[str, Any], status_error: Exception | None = None
    ):
        self._json_data = json_data
        self._status_error = status_error

    def raise_for_status(self) -> None:
        if self._status_error:
            raise self._status_error

    def json(self) -> dict[str, Any]:
        return self._json_data


class MockHTTPClient:
    def __init__(self, response: MockHTTPResponse):
        self.response = response
        self.calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, timeout: int):
        self.calls.append(url)
        return self.response


@pytest.mark.anyio
async def test_node_api_dependency_guards(settings: Settings, mocker: MockerFixture):
    original_node_ui = settings.lnbits_node_ui
    original_public = settings.lnbits_public_node_ui
    try:
        settings.lnbits_node_ui = True
        funding_source = FakeFundingSource([], None)
        mocker.patch(
            "lnbits.core.views.node_api.get_funding_source",
            return_value=funding_source,
        )
        with pytest.raises(HTTPException) as excinfo:
            node_api.require_node()
        assert excinfo.value.status_code == 501

        node_enabled_source = FakeFundingSource(
            [Feature.nodemanager], lambda wallet: "fake-node"
        )
        mocker.patch(
            "lnbits.core.views.node_api.get_funding_source",
            return_value=node_enabled_source,
        )
        settings.lnbits_node_ui = False
        with pytest.raises(HTTPException) as disabled:
            node_api.require_node()
        assert disabled.value.status_code == 503

        settings.lnbits_node_ui = True
        assert node_api.require_node() == "fake-node"

        settings.lnbits_public_node_ui = False
        with pytest.raises(HTTPException) as public_disabled:
            node_api.check_public()
        assert public_disabled.value.status_code == 503
    finally:
        settings.lnbits_node_ui = original_node_ui
        settings.lnbits_public_node_ui = original_public


@pytest.mark.anyio
async def test_node_api_route_functions_with_fake_node(
    settings: Settings,
    mocker: MockerFixture,
):
    fake_node = FakeNode()
    node = cast(Node, fake_node)
    original_transactions = settings.lnbits_node_ui_transactions
    settings.lnbits_node_ui_transactions = True
    rank_response = MockHTTPResponse(
        {
            "noderank": {
                "capacity": 1,
                "channelcount": 2,
                "age": 3,
                "growth": 4,
                "availability": 5,
            }
        }
    )
    mocker.patch(
        "lnbits.core.views.node_api.httpx.AsyncClient",
        return_value=MockHTTPClient(rank_response),
    )

    try:
        assert await node_api.api_get_ok() is None

        public_info = await node_api.api_get_public_info(node=node)
        assert public_info.backend_name == "FakeNode"

        info = await node_api.api_get_info(node=node)
        assert info is not None
        assert info.id == "node-id"

        channels = await node_api.api_get_channels(node=node)
        assert channels is not None
        assert channels[0].id == "chan-1"

        channel = await node_api.api_get_channel("chan-1", node=node)
        assert channel is not None
        assert channel.peer_id == "peer-1"

        created = await node_api.api_create_channel(
            node=node,
            peer_id="peer-1",
            funding_amount=10_000,
            push_amount=100,
            fee_rate=5,
        )
        assert created.output_index == 0

        deleted = await node_api.api_delete_channel(
            short_id="123x1x0",
            funding_txid=None,
            output_index=None,
            force=True,
            node=node,
        )
        assert deleted is not None
        assert deleted[0].id == "chan-1"

        await node_api.api_set_channel_fees(
            "chan-1",
            node=node,
            fee_ppm=42,
            fee_base_msat=7,
        )
        assert fake_node.fees_updated == ("chan-1", 7, 42)

        payments = await node_api.api_get_payments(node=node, filters=Filters())
        assert payments is not None
        assert payments.total == 1

        invoices = await node_api.api_get_invoices(node=node, filters=Filters())
        assert invoices is not None
        assert invoices.total == 1

        peers = await node_api.api_get_peers(node=node)
        assert peers[0].id == "peer-1"

        connect = await node_api.api_connect_peer(
            uri="peer-1@127.0.0.1:9735", node=node
        )
        assert connect["uri"] == "peer-1@127.0.0.1:9735"

        disconnect = await node_api.api_disconnect_peer("peer-1", node=node)
        assert disconnect["peer_id"] == "peer-1"

        rank = await node_api.api_get_1ml_stats(node=node)
        assert rank is not None
        rank_data = node_api.NodeRank.parse_obj(rank)
        assert rank_data.channelcount == 2
    finally:
        settings.lnbits_node_ui_transactions = original_transactions


@pytest.mark.anyio
async def test_node_api_transactions_and_rank_errors(
    settings: Settings,
    mocker: MockerFixture,
):
    fake_node = FakeNode()
    node = cast(Node, fake_node)
    original_transactions = settings.lnbits_node_ui_transactions
    settings.lnbits_node_ui_transactions = False

    request = httpx.Request("GET", f"https://1ml.com/node/{uuid4().hex}/json")
    mocker.patch(
        "lnbits.core.views.node_api.httpx.AsyncClient",
        return_value=MockHTTPClient(
            MockHTTPResponse(
                {},
                status_error=httpx.HTTPStatusError(
                    "not found", request=request, response=httpx.Response(404)
                ),
            )
        ),
    )

    try:
        with pytest.raises(HTTPException) as payments:
            await node_api.api_get_payments(node=node, filters=Filters())
        assert payments.value.status_code == 503

        with pytest.raises(HTTPException) as invoices:
            await node_api.api_get_invoices(node=node, filters=Filters())
        assert invoices.value.status_code == 503

        with pytest.raises(HTTPException) as rank:
            await node_api.api_get_1ml_stats(node=node)
        assert rank.value.status_code == 404
        assert rank.value.detail == "Node not found on 1ml.com"
    finally:
        settings.lnbits_node_ui_transactions = original_transactions
