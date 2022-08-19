from http import HTTPStatus

from fastapi import Request, FastAPI, File, UploadFile
from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user, get_wallet
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

from loguru import logger

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
    except:
        pass

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
@podcast_ext.post("/api/v1/pods/{pod_id}", status_code=HTTPStatus.OK)
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
            {**eps.dict()}
            for eps in await get_Episodes(wallet_ids)
        ]
    except:
        pass


@podcast_ext.get("/api/v1/eps/{eps_id}", status_code=HTTPStatus.OK)
async def api_eps_retrieve(
    r: Request, eps_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    eps = await get_Episode(eps_id)

    if not eps:
        raise HTTPException(
            detail="Episode does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if eps.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your episode.", status_code=HTTPStatus.FORBIDDEN
        )

    return {**eps.dict()}


@podcast_ext.post("/api/v1/eps", status_code=HTTPStatus.CREATED)
@podcast_ext.post("/api/v1/eps/{eps_id}", status_code=HTTPStatus.OK)
async def api_eps_create_or_update(
    data: CreateEpisodeData,
    request: Request,
    eps_id=None,
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    pod = get_Podcast(data.podcast)
    pod.wallet
    wallet = await get_wallet(pod.wallet)
    if not wallet:
        raise HTTPException(
            detail="Wallet not found", status_code=HTTPStatus.NOT_FOUND
        )
    if eps_id:
        pod = await get_Episode(eps_id)

        if not eps:
            raise HTTPException(
                detail="Episode eps does not exist.", status_code=HTTPStatus.NOT_FOUND
            )

        if eps.wallet != wallet.wallet.id:
            raise HTTPException(
                detail="Not your episode.", status_code=HTTPStatus.FORBIDDEN
            )

        eps = await update_Episode(**data.dict(), eps_id=eps_id)
    else:
        eps = await create_Episode(data, wallet_id=wallet.wallet.id)
    return {**eps.dict()}


@podcast_ext.delete("/api/v1/eps/{eps_id}", status_code=HTTPStatus.OK)
async def api_eps_delete(eps_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    eps = await get_Episode(eps_id)

    if not eps:
        raise HTTPException(
            detail="Episode does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if eps.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your episode.", status_code=HTTPStatus.FORBIDDEN
        )

    await delete_Episode(eps_id)
    return {"success": True}


@podcast_ext.post("/api/v1/files/")
async def create_upload_file(file: UploadFile = File(...), episodename: str = Query(None)):
    episode = await get_Episode(episodename)
    if not episode:
        raise HTTPException(
            detail="Episode does not exist.", status_code=HTTPStatus.NOT_FOUND
        )
    try:
        contents = file.file.read()
        with open(f"lnbits/extensions/podcast/podcasts/{episodename}-{file.filename}", 'wb') as f:
            f.write(contents)
    except Exception:
        return {"message": "There was an error uploading the file"}
    finally:
        file.file.close()

    return {"message": f"Successfully uploaded {file.filename}"}