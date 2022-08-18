from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.utils.exchange_rates import currencies, get_fiat_rate_satoshis

from . import podcast_ext
from .crud import (
    create_Podcast,
    delete_Podcast,
    get_Podcast,
    get_Podcasts,
    update_Podcast,
    create_Episode,
    delete_Episode,
    get_Episode,
    get_Episodes,
    update_Episode,
)
from .models import CreatePodcastData, CreateEpisodeData


#########PODCASTS#########

@podcast_ext.get("/api/v1/pods", status_code=HTTPStatus.OK)
async def api_pods(
    req: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    try:
        return [
            {**pod.dict()}
            for pod in await get_Podcasts(wallet_ids)
        ]

    except LnurlInvalidUrl:
        raise HTTPException(
            status_code=HTTPStatus.UPGRADE_REQUIRED,
            detail="LNURLs need to be delivered over a publically accessible `https` domain or Tor.",
        )


@podcast_ext.get("/api/v1/pods/{pod_id}", status_code=HTTPStatus.OK)
async def api_pod_retrieve(
    r: Request, pod_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    pod = await get_Podcast(pod_id)

    if not pod:
        raise HTTPException(
            detail="Podcast pod does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if pod.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your Podcast pod.", status_code=HTTPStatus.FORBIDDEN
        )

    return {**pod.dict()}


@podcast_ext.post("/api/v1/pods", status_code=HTTPStatus.CREATED)
@podcast_ext.put("/api/v1/pods/{pod_id}", status_code=HTTPStatus.OK)
async def api_pod_create_or_update(
    data: CreatePodcastData,
    request: Request,
    pod_id=None,
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    if pod_id:
        pod = await get_Podcast(pod_id)

        if not pod:
            raise HTTPException(
                detail="Podcast pod does not exist.", status_code=HTTPStatus.NOT_FOUND
            )

        if pod.wallet != wallet.wallet.id:
            raise HTTPException(
                detail="Not your Podcast pod.", status_code=HTTPStatus.FORBIDDEN
            )

        pod = await update_Podcast(**data.dict(), pod_id=pod_id)
    else:
        pod = await create_Podcast(data, wallet_id=wallet.wallet.id)
    return {**pod.dict()}


@podcast_ext.delete("/api/v1/pods/{pod_id}", status_code=HTTPStatus.OK)
async def api_pod_delete(pod_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    pod = await get_Podcast(pod_id)

    if not pod:
        raise HTTPException(
            detail="Podcast pod does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if pod.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your Podcast pod.", status_code=HTTPStatus.FORBIDDEN
        )

    await delete_Podcast(pod_id)
    return {"success": True}


##########EPISODES##########

@podcast_ext.get("/api/v1/eps", status_code=HTTPStatus.OK)
async def api_eps(
    req: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    try:
        return [
            {**pod.dict()}
            for pod in await get_Podcasts(wallet_ids)
        ]

    except LnurlInvalidUrl:
        raise HTTPException(
            status_code=HTTPStatus.UPGRADE_REQUIRED,
            detail="LNURLs need to be delivered over a publically accessible `https` domain or Tor.",
        )


@podcast_ext.get("/api/v1/eps/{eps_id}", status_code=HTTPStatus.OK)
async def api_eps_retrieve(
    r: Request, pod_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    pod = await get_Podcast(pod_id)

    if not pod:
        raise HTTPException(
            detail="Podcast pod does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if pod.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your Podcast pod.", status_code=HTTPStatus.FORBIDDEN
        )

    return {**pod.dict()}


@podcast_ext.post("/api/v1/eps", status_code=HTTPStatus.CREATED)
@podcast_ext.put("/api/v1/eps/{pod_id}", status_code=HTTPStatus.OK)
async def api_eps_create_or_update(
    data: CreatePodcastData,
    request: Request,
    pod_id=None,
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    if pod_id:
        pod = await get_Podcast(pod_id)

        if not pod:
            raise HTTPException(
                detail="Podcast pod does not exist.", status_code=HTTPStatus.NOT_FOUND
            )

        if pod.wallet != wallet.wallet.id:
            raise HTTPException(
                detail="Not your Podcast pod.", status_code=HTTPStatus.FORBIDDEN
            )

        pod = await update_Podcast(**data.dict(), pod_id=pod_id)
    else:
        pod = await create_Podcast(data, wallet_id=wallet.wallet.id)
    return {**pod.dict()}


@podcast_ext.delete("/api/v1/eps/{pod_id}", status_code=HTTPStatus.OK)
async def api_eps_delete(pod_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    pod = await get_Podcast(pod_id)

    if not pod:
        raise HTTPException(
            detail="Podcast pod does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if pod.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your Podcast pod.", status_code=HTTPStatus.FORBIDDEN
        )

    await delete_Podcast(pod_id)
    return {"success": True}
