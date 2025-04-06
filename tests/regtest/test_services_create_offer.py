import pytest

from lnbits.core.services import create_offer, disable_offer
from lnbits.wallets import get_funding_source, set_funding_source
from lnbits.wallets.base import OfferStatus

description = "test create offer"


@pytest.mark.anyio
async def test_create_offer():
    set_funding_source("CoreLightningWallet")

    invoice_offer = await create_offer(
        wallet_id="10c8094f9d1c4ab4b9e3dfe964527297",
        amount_sat=1000,
        memo=description,
        single_use=True,
    )
    """
    offer = decode(invoice_offer.bolt12)
    assert offer.amount_msat == 1000000
    assert offer.description == description
    """

    await disable_offer(
        wallet_id="10c8094f9d1c4ab4b9e3dfe964527297", offer_id=invoice_offer.offer_id
    )

    funding_source = get_funding_source()
    status = await funding_source.get_offer_status(invoice_offer.offer_id)
    assert isinstance(status, OfferStatus)
    assert not status.active
    assert not status.used
