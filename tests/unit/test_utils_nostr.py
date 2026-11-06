import pytest

from lnbits.utils.nostr import normalize_identifier, validate_identifier


@pytest.mark.parametrize("local_part", ["alice", "john-doe", "a.b_c-d", "Bob-42"])
def test_validate_identifier_accepts_nip05_characters(local_part: str):
    validate_identifier(local_part)


@pytest.mark.parametrize("local_part", ["", "bad!", "white space", "a+b", "ü"])
def test_validate_identifier_rejects_other_characters(local_part: str):
    with pytest.raises(ValueError):
        validate_identifier(local_part)


def test_normalize_identifier_keeps_hyphens():
    assert normalize_identifier("John-Doe@example.com") == "john-doe"
