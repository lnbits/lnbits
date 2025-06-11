import pytest

from lnbits.utils.crypto import AESCipher


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
