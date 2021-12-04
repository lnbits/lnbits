import pytest

from lnbits.extensions.autopay.utils import * 


@pytest.mark.skip(reason="Requires 2 lnbits instances running")
async def test_basic_lnurl_payment():
    """ Does HTTP requests to LNBits."""
    test_lnurl="LNURL1DP68GURN8GHJ7MR0VDSKC6R0WD6ZUMR0VDSKCER0D4SKJM36X5CRQVP0D3H82UNVWQHKZURF9AMRZTMVDE6HYMP0XURJK2EN"
    wallet_alice1_id = "9e75ffeaee01409ab2f905dd8336f0ae"
    wallet_dave1_id = "fe39ffc74ce7486fb76202f2c4cf58dc"


    amount_msat = 100*1000
    comment = ""
    pay_info = await lnurl_scan(test_lnurl)
    invoice = await lnurl_get_invoice(pay_info["callback"], amount_msat, comment, pay_info["description_hash"])
    payment_hash = await pay_invoice_with_wallet(wallet_dave1_id, invoice["pr"], comment)

    print("RESULT", payment_hash)
