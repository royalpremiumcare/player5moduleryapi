"""Canonical customer identity: phone key and name matching. Pure, no I/O."""
from typing import Literal, Optional

Country = Literal["TR", "UK"]

_TR_FOLD = str.maketrans("çğıöşü", "cgiosu")


def country_for_currency(currency: Optional[str]) -> Country:
    return "UK" if currency == "GBP" else "TR"


def phone_key(phone: Optional[str], default_country: Country = "TR") -> Optional[str]:
    digits = "".join(ch for ch in (phone or "") if ch in "0123456789")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) < 10:
        return None
    if digits.startswith("0"):
        if default_country == "TR" and len(digits) == 11:
            return "90" + digits[1:]
        if default_country == "UK" and len(digits) == 11 and digits[1] == "7":
            return "44" + digits[1:]
        return None
    if default_country == "TR" and len(digits) == 10 and digits[0] == "5":
        return "90" + digits
    if default_country == "UK" and len(digits) == 10 and digits[0] == "7":
        return "44" + digits
    if 11 <= len(digits) <= 15:
        return digits
    return None


def normalize_name(name: Optional[str]) -> str:
    text = (name or "").replace("İ", "i").replace("I", "ı").lower()
    text = text.replace("i̇", "i").translate(_TR_FOLD)
    words = text.split()
    if words and words[-1] == "musteri":
        words.pop()
    return " ".join(words)


def names_match(a: Optional[str], b: Optional[str], *, allow_subset: bool) -> bool:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if allow_subset:
        ta, tb = set(na.split()), set(nb.split())
        return ta <= tb or tb <= ta
    return False
