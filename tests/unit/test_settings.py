import pytest

from lnbits.settings import RedirectPath

lnurlp_redirect_path = {
    "from_path": "/.well-known/lnurlp",
    "redirect_to_path": "/api/v1/well-known",
}

lnaddress_redirect_path = {
    "from_path": "/.well-known/lnurlp",
    "redirect_to_path": "/api/v1/well-known",
}

nostrrelay_redirect_path = {
    "from_path": "/",
    "redirect_to_path": "/api/v1/relay-info",
    "header_filters": {"accept": "application/nostr+json"},
}


@pytest.mark.asyncio
async def test_redirect_path_in_conflict():

    redirect_path_lnurl = RedirectPath(ext_id="lnurlp", **lnurlp_redirect_path)
    redirect_path_lnaddress = RedirectPath(
        ext_id="lnaddress", **lnaddress_redirect_path
    )
    nostrrelay_path_lnurl = RedirectPath(ext_id="lnurlp", **nostrrelay_redirect_path)

    assert not redirect_path_lnurl.in_conflict(
        redirect_path_lnurl
    ), "Path is not in conflict with itself."
    assert not redirect_path_lnaddress.in_conflict(
        redirect_path_lnaddress
    ), "Path is not in conflict with itself."
    assert not nostrrelay_path_lnurl.in_conflict(
        nostrrelay_path_lnurl
    ), "Path is not in conflict with itself."

    assert redirect_path_lnurl.in_conflict(
        redirect_path_lnaddress
    ), "Paths are in conflict."

    assert redirect_path_lnaddress.in_conflict(
        redirect_path_lnurl
    ), "Paths are in conflict (commutative)."

    assert not redirect_path_lnurl.in_conflict(
        nostrrelay_path_lnurl
    ), "Paths are not in conflict."

    assert not nostrrelay_path_lnurl.in_conflict(
        redirect_path_lnurl
    ), "Paths are not in conflict (commutative)."
