import re
from collections.abc import Iterable
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
AADHAAR_RE = re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")
CREDIT_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
INDIA_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\d)")
PHONE_RE = re.compile(
    r"(?<![A-Z0-9])(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{4}(?![A-Z0-9])",
    re.IGNORECASE,
)


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _is_luhn_valid(value: str) -> bool:
    digits = [int(character) for character in _digits(value)]
    if len(digits) < 13 or len(digits) > 19:
        return False

    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _mask_credit_card(match: re.Match[str]) -> str:
    value = match.group(0)
    if not _is_luhn_valid(value):
        return value
    return "[PAYMENT_CARD]"


def _mask_phone(match: re.Match[str]) -> str:
    value = match.group(0)
    digit_count = len(_digits(value))
    if digit_count < 10 or digit_count > 13:
        return value
    return "[PHONE]"


def mask_sensitive_data(text: str | None) -> str:
    if not text:
        return ""

    masked = EMAIL_RE.sub("[EMAIL]", text)
    masked = PAN_RE.sub("[PAN]", masked)
    masked = SSN_RE.sub("[SSN]", masked)
    masked = CREDIT_CARD_RE.sub(_mask_credit_card, masked)
    masked = AADHAAR_RE.sub("[AADHAAR]", masked)
    masked = INDIA_PHONE_RE.sub("[PHONE]", masked)
    masked = PHONE_RE.sub(_mask_phone, masked)
    return masked


def mask_citation_payloads(citations: Iterable[Any] | None) -> list[dict[str, Any]]:
    masked_citations = []
    for citation in citations or []:
        if hasattr(citation, "model_dump"):
            citation_data = citation.model_dump()
        else:
            citation_data = dict(citation)
        if "excerpt" in citation_data:
            citation_data["excerpt"] = mask_sensitive_data(citation_data["excerpt"])
        masked_citations.append(citation_data)
    return masked_citations
