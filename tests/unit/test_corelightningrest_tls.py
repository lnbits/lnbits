import pytest

from lnbits.wallets.corelightningrest import CoreLightningRestWallet


@pytest.mark.parametrize(
    ("certificate", "verify"),
    [(None, True), ("", True), ("/custom/ca.pem", "/custom/ca.pem")],
)
def test_corelightningrest_verifies_tls_by_default(
    settings, mocker, certificate, verify
):
    settings.corelightning_rest_url = "https://cln.example.com"
    settings.corelightning_rest_macaroon = "test-macaroon"
    settings.corelightning_rest_cert = certificate
    mocker.patch(
        "lnbits.wallets.corelightningrest.load_macaroon", return_value="test-macaroon"
    )
    client = mocker.patch("lnbits.wallets.corelightningrest.httpx.AsyncClient")

    CoreLightningRestWallet()

    assert client.call_args.kwargs["verify"] == verify
    assert client.call_args.kwargs["verify"] is not False
