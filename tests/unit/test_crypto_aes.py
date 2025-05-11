import pytest

from lnbits.utils.crypto import AESCipher


@pytest.mark.anyio
async def test_aes_encrypt_decrypt():
    aes = AESCipher(b"my_secret_key")
    original_text = b"Hello, World!"
    encrypted_text = aes.encrypt(original_text)
    decrypted_text = aes.decrypt(encrypted_text)
    assert original_text == decrypted_text
