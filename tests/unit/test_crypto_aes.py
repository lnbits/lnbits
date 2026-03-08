from base64 import b64encode
from hashlib import sha256

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.utils.crypto import (
    AESCipher,
    fake_privkey,
    random_secret_and_hash,
    verify_preimage,
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "key",
    [
        "normal_string",
        b"normal_bytes",
        b"hex_string".hex(),
    ],
)
async def test_aes_encrypt_decrypt(key):
    aes = AESCipher(key)
    original_text = "Hello, World!"
    encrypted_text = aes.encrypt(original_text.encode())
    decrypted_text = aes.decrypt(encrypted_text)
    assert original_text == decrypted_text


def test_random_secret_and_hash():
    secret, payment_hash = random_secret_and_hash(16)

    assert len(secret) == 32
    assert payment_hash == sha256(bytes.fromhex(secret)).hexdigest()


def test_fake_privkey_is_deterministic():
    assert fake_privkey("secret") == fake_privkey("secret")
    assert fake_privkey("secret") != fake_privkey("other-secret")


def test_verify_preimage_success_and_failure():
    preimage = "00" * 32
    payment_hash = sha256(bytes.fromhex(preimage)).hexdigest()

    assert verify_preimage(preimage, payment_hash) is True
    assert verify_preimage(preimage, "0" * 64) is False


@pytest.mark.anyio
async def test_aes_urlsafe_encrypt_decrypt():
    aes = AESCipher("normal_string")

    encrypted_text = aes.encrypt(b"url-safe", urlsafe=True)

    assert aes.decrypt(encrypted_text, urlsafe=True) == "url-safe"


def test_aes_derive_iv_and_key_requires_eight_byte_salt():
    aes = AESCipher("normal_string")

    with pytest.raises(ValueError, match="Salt must be 8 bytes"):
        aes.derive_iv_and_key(b"short")


def test_aes_decrypt_rejects_invalid_salt_prefix():
    aes = AESCipher("normal_string")
    encrypted_text = b64encode(b"NotSalted__12345678ciphertext").decode()

    with pytest.raises(ValueError, match="Invalid salt."):
        aes.decrypt(encrypted_text)


def test_aes_decrypt_raises_for_cipher_errors(mocker: MockerFixture):
    aes = AESCipher("normal_string")
    fake_cipher = mocker.Mock()
    fake_cipher.decrypt.side_effect = RuntimeError("boom")

    mocker.patch.object(
        aes,
        "derive_iv_and_key",
        return_value=(b"0" * aes.block_size, b"1" * 32),
    )
    mocker.patch("lnbits.utils.crypto.AES.new", return_value=fake_cipher)

    encrypted_text = b64encode(b"Salted__12345678ciphertext").decode()

    with pytest.raises(ValueError, match="Could not decrypt payload"):
        aes.decrypt(encrypted_text)


def test_aes_decrypt_raises_for_invalid_utf8_output(mocker: MockerFixture):
    aes = AESCipher("normal_string")
    fake_cipher = mocker.Mock()
    fake_cipher.decrypt.return_value = b"\xff\x01"

    mocker.patch.object(
        aes,
        "derive_iv_and_key",
        return_value=(b"0" * aes.block_size, b"1" * 32),
    )
    mocker.patch("lnbits.utils.crypto.AES.new", return_value=fake_cipher)

    encrypted_text = b64encode(b"Salted__12345678ciphertext").decode()

    with pytest.raises(ValueError, match="invalid UTF-8 data"):
        aes.decrypt(encrypted_text)
