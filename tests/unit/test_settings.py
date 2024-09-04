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


@pytest.fixture()
def lnurlp():
    return RedirectPath(ext_id="lnurlp", **lnurlp_redirect_path)


@pytest.fixture()
def lnaddress():
    return RedirectPath(ext_id="lnaddress", **lnaddress_redirect_path)


@pytest.fixture()
def nostrrelay():
    return RedirectPath(ext_id="nostrrelay", **nostrrelay_redirect_path)


@pytest.mark.asyncio
async def test_redirect_path_self_not_in_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert not lnurlp.in_conflict(lnurlp), "Path is not in conflict with itself."
    assert not lnaddress.in_conflict(lnaddress), "Path is not in conflict with itself."
    assert not nostrrelay.in_conflict(
        nostrrelay
    ), "Path is not in conflict with itself."

    assert not lnurlp.in_conflict(nostrrelay), "Paths are not in conflict."

    assert not nostrrelay.in_conflict(lnurlp), "Paths are not in conflict."


@pytest.mark.asyncio
async def test_redirect_path_not_in_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):

    assert not lnurlp.in_conflict(nostrrelay), "Paths are not in conflict."

    assert not nostrrelay.in_conflict(lnurlp), "Paths are not in conflict."

    assert not lnaddress.in_conflict(nostrrelay), "Paths are not in conflict."

    assert not nostrrelay.in_conflict(lnaddress), "Paths are not in conflict."


@pytest.mark.asyncio
async def test_redirect_path_in_conflict(lnurlp: RedirectPath, lnaddress: RedirectPath):
    assert lnurlp.in_conflict(lnaddress), "Paths are in conflict."
    assert lnaddress.in_conflict(lnurlp), "Paths are in conflict."


@pytest.mark.asyncio
async def test_redirect_path_find_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert lnurlp.find_in_conflict([nostrrelay, lnaddress]), "Paths are in conflict."
    assert lnurlp.find_in_conflict([lnaddress, nostrrelay]), "Paths are in conflict."
    assert lnaddress.find_in_conflict([nostrrelay, lnurlp]), "Paths are in conflict."
    assert lnaddress.find_in_conflict([lnurlp, nostrrelay]), "Paths are in conflict."


@pytest.mark.asyncio
async def test_redirect_path_find_no_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert not nostrrelay.find_in_conflict(
        [lnurlp, lnaddress]
    ), "Paths are not in conflict."
    assert not lnurlp.find_in_conflict([nostrrelay]), "Paths are not in conflict."
    assert not lnaddress.find_in_conflict([nostrrelay]), "Paths are not in conflict."
