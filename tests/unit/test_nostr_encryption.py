import pytest
from coincurve import PublicKey

from lnbits.utils.nostr import decrypt_content, encrypt_content, get_shared_x
from lnbits.wallets.nwc import NIP44Encryption

GENERATOR_X = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"


@pytest.mark.parametrize("prefix", ["02", "03"])
@pytest.mark.parametrize("secret", ["01", "00" * 30 + "01", "00" * 31 + "01"])
def test_nip04_content_compatibility(mocker, prefix, secret):
    public_key = PublicKey(bytes.fromhex(prefix + GENERATOR_X))
    mocker.patch("lnbits.utils.nostr.Random.new").return_value.read.return_value = (
        bytes(16)
    )
    ciphertext = "Wq/YEnzybbrOBFdPOqh3og==?iv=AAAAAAAAAAAAAAAAAAAAAA=="

    assert get_shared_x(public_key, secret).hex() == GENERATOR_X
    assert encrypt_content("hello", public_key, secret) == ciphertext
    assert decrypt_content(ciphertext, public_key, secret) == "hello"


@pytest.mark.parametrize("prefix", ["02", "03"])
def test_nip44_conversation_key_vector(prefix):
    # NIP-44 v2 get_conversation_key test vector.
    secret = "315e59ff51cb9209768cf7da80791ddcaae56ac9775eb25b6dee1234bc5d2268"
    public_key = PublicKey(
        bytes.fromhex(
            prefix + "c2f9d9948dc8c7c38321e4b85c8558872eafa0641cd269db76848a6073e69133"
        )
    )

    assert NIP44Encryption._get_conversation_key(public_key, secret).hex() == (
        "3dfef0ce2a4d80a25e7a328accf73448ef67096f65f79588e358d9a0eb9013f1"
    )


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "00" * 32,
        "ff" * 32,
        "fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141",
        "01" * 33,
        "00" + "01" * 32,
    ],
)
def test_shared_x_rejects_invalid_private_keys(secret):
    public_key = PublicKey(bytes.fromhex("02" + GENERATOR_X))

    with pytest.raises(ValueError):
        get_shared_x(public_key, secret)
