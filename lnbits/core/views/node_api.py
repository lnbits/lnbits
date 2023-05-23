from typing import Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from lnbits.decorators import check_admin, parse_filters
from lnbits.nodes import get_node_class
from lnbits.settings import settings

from ...db import Filters, Page
from ...nodes.base import (
    Node,
    NodeChannelsResponse,
    NodeInfoResponse,
    NodeInvoice,
    NodeInvoiceFilters,
    NodePayment,
    NodePaymentsFilters,
    NodePeerInfo,
    PublicNodeInfo,
)
from .. import core_app


class NodeInfo(NodeInfoResponse):
    pass


def require_node():
    NODE = get_node_class()
    if not NODE:
        raise HTTPException(
            status_code=400,
            detail="Active backend does not implement Node API",
        )
    if not settings.lnbits_node_ui:
        raise HTTPException(
            status_code=404,
            detail="Not enabled",
        )
    return NODE


def check_public():
    if not (settings.lnbits_node_ui and settings.lnbits_public_node_ui):
        raise HTTPException(
            status_code=404,
            detail="Not enabled",
        )


node_api = APIRouter(prefix="/node/api/v1", dependencies=[Depends(check_admin)])
public_node_api = APIRouter(
    prefix="/node/public/api/v1", dependencies=[Depends(check_public)]
)


@node_api.get(
    "/ok",
    description="Check if node api can be enabled",
    status_code=200,
    dependencies=[Depends(require_node)],
)
async def api_get_ok():
    pass


@public_node_api.get("/info", response_model=PublicNodeInfo)
async def api_get_public_info(node: Node = Depends(require_node)) -> PublicNodeInfo:
    return await node.get_public_info()


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
    peer_id: str = Body(),
    funding_amount: int = Body(),
    push_amount: Optional[int] = Body(None),
    fee_rate: Optional[int] = Body(None),
) -> Optional[NodeChannelsResponse]:
    return await node.open_channel(peer_id, funding_amount, push_amount, fee_rate)


@node_api.delete("/channels")
async def api_delete_channel(
    node: Node = Depends(require_node),
    short_id: Optional[str] = Body(None),
    funding_txid: Optional[str] = Body(None),
    force: bool = Body(False),
) -> Optional[NodeChannelsResponse]:
    return await node.close_channel(short_id, funding_txid, force)


@node_api.get("/payments", response_model=Page[NodePayment])
async def api_get_payments(
    node: Node = Depends(require_node),
    filters: Filters = Depends(parse_filters(NodePaymentsFilters)),
) -> Optional[Page[NodePayment]]:
    return await node.get_payments(filters)


@node_api.get("/invoices", response_model=Page[NodeInvoice])
async def api_get_invoices(
    node: Node = Depends(require_node),
    filters: Filters = Depends(parse_filters(NodeInvoiceFilters)),
) -> Optional[Page[NodeInvoice]]:
    return await node.get_invoices(filters)


@node_api.get("/peers", response_model=list[NodePeerInfo])
async def api_get_peers(node: Node = Depends(require_node)) -> list[NodePeerInfo]:
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


# Same for public and private api
@node_api.get(
    "/rank",
    description="Retrieve node ranks from https://1ml.com",
    response_model=Optional[NodeRank],
)
@public_node_api.get(
    "/rank",
    description="Retrieve node ranks from https://1ml.com",
    response_model=Optional[NodeRank],
)
async def api_get_1ml_stats(node: Node = Depends(require_node)) -> Optional[NodeRank]:
    node_id = await node.get_id()
    async with httpx.AsyncClient() as client:
        # node_id = "026165850492521f4ac8abd9bd8088123446d126f648ca35e60f88177dc149ceb2"
        r = await client.get(url=f"https://1ml.com/node/{node_id}/json", timeout=15)
        try:
            r.raise_for_status()
            return r.json()["noderank"]
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=404, detail="Node not found on 1ml.com")


core_app.include_router(node_api)
core_app.include_router(public_node_api)
