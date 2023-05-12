from typing import Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from lnbits.decorators import check_admin
from lnbits.settings import get_node_class

from ...nodes.base import (
    Node,
    NodeChannelsResponse,
    NodeInfoResponse,
    NodePayment,
    NodePeerInfo,
)
from .. import core_app

node_api = APIRouter(prefix="/node/api/v1", dependencies=[Depends(check_admin)])


class NodeInfo(NodeInfoResponse):
    pass


def require_node():
    NODE = get_node_class()
    if not NODE:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Active backend doesnt support Node apis",
        )
    return NODE


@node_api.get("/info")
async def api_get_info(
    node: Node = Depends(require_node),
) -> Optional[NodeInfoResponse]:
    return await node.get_info()


@node_api.get("/channels")
async def api_get_channels(
    node: Node = Depends(require_node),
) -> Optional[NodeChannelsResponse]:
    return await node.get_channels()


@node_api.post("/channels")
async def api_create_channel(
    node: Node = Depends(require_node),
    peer_id: str = Body(embed=True),
    funding_amount: int = Body(embed=True),
) -> Optional[NodeChannelsResponse]:
    return await node.open_channel(peer_id, funding_amount)


@node_api.delete("/channels")
async def api_delete_channel(
    node: Node = Depends(require_node), channel_id: str = Body(embed=True)
) -> Optional[NodeChannelsResponse]:
    return await node.close_channel(channel_id)


@node_api.get("/transactions")
async def api_get_transacions(
    node: Node = Depends(require_node),
) -> Optional[list[NodePayment]]:
    return await node.get_payments()


@node_api.get("/peers", response_model=list[NodePeerInfo])
async def api_get_payments(node: Node = Depends(require_node)) -> list[NodePeerInfo]:
    return await node.get_peers()


@node_api.post("/peers/connect")
async def api_connect_peer(
    uri: str = Body(embed=True), node: Node = Depends(require_node)
):
    return await node.connect_peer(uri)


class NodeRank(BaseModel):
    capacity: Optional[int]
    channelcount: Optional[int]
    age: Optional[int]
    growth: Optional[int]
    availability: Optional[int]


@node_api.get(
    "/rank",
    description="Retrieve node ranks from https://1ml.com",
    response_model=Optional[NodeRank],
)
async def api_get_1ml_stats(node=Depends(require_node)) -> Optional[NodeRank]:
    node_id = await node.get_id()
    async with httpx.AsyncClient() as client:
        r = await client.get(url=f"https://1ml.com/node/{node_id}/json", timeout=15)
        try:
            r.raise_for_status()
            return r.json()["noderank"]
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=404, detail="Node not found on 1ml.com")


core_app.include_router(node_api)
