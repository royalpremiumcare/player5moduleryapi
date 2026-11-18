import pytest

from customer_identity import (
    country_for_currency,
    names_match,
    normalize_name,
    phone_key,
)


@pytest.mark.parametrize(
    "phone,country,expected",
    [
        ("0555 111 22 33", "TR", "905551112233"),
        ("5551112233", "TR", "905551112233"),
        ("+90 555 111 22 33", "TR", "905551112233"),
        ("00905551112233", "TR", "905551112233"),
        ("07700 900123", "UK", "447700900123"),
        ("7700900123", "UK", "447700900123"),
        ("+44 7700 900123", "TR", "447700900123"),
        ("+49 1512 3456789", "TR", "4915123456789"),
        ("0", "TR", None),
        ("00", "TR", None),
        ("12345", "TR", None),
        (None, "TR", None),
        ("055511122334455", "TR", None),
    ],
)
def test_phone_key_rules(phone, country, expected):
    assert phone_key(phone, country) == expected


def test_country_for_currency():
    assert country_for_currency("GBP") == "UK"
    assert country_for_currency("TRY") == "TR"
    assert country_for_currency(None) == "TR"
    assert country_for_currency("EUR") == "TR"


def test_normalize_name_turkish_folding():
    assert normalize_name("  İrem   ÇELİK ") == "irem celik"
    assert normalize_name("IŞIK Öğüt") == "isik ogut"
    assert normalize_name(None) == ""


def test_names_match():
    assert names_match("Canan Çelik", "canan celik Müşteri", allow_subset=False)
    assert names_match("Alara", "Alara Kaya", allow_subset=True)
    assert not names_match("Alara", "Alara Kaya", allow_subset=False)
    assert not names_match("Elif", "Elif Naz", allow_subset=False)
    assert names_match("İrem", "irem", allow_subset=False)
    assert not names_match("Makbule", "Kadir Burak", allow_subset=False)
    assert not names_match("Makbule", "Kadir Burak", allow_subset=True)
    assert not names_match("", "", allow_subset=True)


from customer_identity import phone_variants


@pytest.mark.parametrize(
    "key,expected",
    [
        ("905551112233", {"905551112233", "05551112233", "5551112233", "+905551112233"}),
        ("447700900123", {"447700900123", "07700900123", "+447700900123"}),
        ("4915123456789", {"4915123456789", "+4915123456789"}),
    ],
)
def test_phone_variants_cover_stored_formats(key, expected):
    assert set(phone_variants(key)) == expected


def test_phone_variants_roundtrip_to_same_key():
    for v in phone_variants("905551112233"):
        assert phone_key(v, "TR") == "905551112233"
