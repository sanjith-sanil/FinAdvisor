import pytest
from app.services.crypto_service import encrypt_text, decrypt_text


def test_encrypt_and_decrypt_symmetry():
    plaintext = "my_secret_password_123"
    encrypted = encrypt_text(plaintext)
    assert encrypted != plaintext
    decrypted = decrypt_text(encrypted)
    assert decrypted == plaintext


def test_encrypt_decrypt_special_characters():
    plaintext = "P@$$w0rd!#%^&*()_+=~`{}[]|:;'<>,.?/"
    encrypted = encrypt_text(plaintext)
    decrypted = decrypt_text(encrypted)
    assert decrypted == plaintext


def test_encrypt_decrypt_unicode():
    plaintext = "₹50,000 paid to स्वाइप मशीन"
    encrypted = encrypt_text(plaintext)
    decrypted = decrypt_text(encrypted)
    assert decrypted == plaintext
