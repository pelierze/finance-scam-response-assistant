"""Local redaction of common sensitive values before external API calls."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RedactionResult:
    text: str
    detected_types: tuple[str, ...]
    redaction_count: int

    @property
    def was_redacted(self) -> bool:
        return bool(self.detected_types)


_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "resident_id",
        "[주민등록번호 마스킹]",
        re.compile(r"(?<!\d)\d{6}\s*[- ]?\s*[1-4]\d{6}(?!\d)"),
    ),
    (
        "email",
        "[이메일 마스킹]",
        re.compile(
            r"(?<![A-Za-z0-9_.+-])"
            r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
            r"(?![A-Za-z0-9_.-])"
        ),
    ),
    (
        "phone",
        "[전화번호 마스킹]",
        re.compile(r"(?<!\d)(?:01[016789])[- ]?\d{3,4}[- ]?\d{4}(?!\d)"),
    ),
    (
        "card",
        "[카드번호 마스킹]",
        re.compile(
            r"(?:(?P<label>카드번호|카드)"
            r"(?P<separator>\s*(?:는|은|가|를|:)?\s*)"
            r"(?P<value>\d{16})(?!\d))|"
            r"(?P<formatted>(?<!\d)(?:\d{4}[- ]){3}\d{4}(?!\d))"
        ),
    ),
    (
        "auth_code",
        "[인증정보 마스킹]",
        re.compile(
            r"(?P<label>인증번호|인증코드|보안코드)"
            r"(?P<separator>\s*(?:는|은|가|:)?\s*)"
            r"(?P<value>[A-Za-z0-9!@#$%^&*]{4,20})",
            re.IGNORECASE,
        ),
    ),
    (
        "password",
        "[비밀번호 마스킹]",
        re.compile(
            r"(?P<label>비밀번호)"
            r"(?P<separator>\s*(?:는|은|가|:)?\s*)"
            r"(?P<value>[A-Za-z0-9!@#$%^&*]{4,20})",
            re.IGNORECASE,
        ),
    ),
    (
        "account",
        "[계좌번호 마스킹]",
        re.compile(
            r"(?P<label>계좌번호|계좌)"
            r"(?P<separator>\s*(?:는|은|가|:)?\s*)"
            r"(?P<value>\d(?:[- ]?\d){7,15})"
        ),
    ),
)


def redact_sensitive_text(text: str) -> RedactionResult:
    """Return text with recognized sensitive values replaced locally.

    Context labels are preserved for authentication and account values so the
    downstream analyzer can still understand that information was shared.
    """

    if not isinstance(text, str):
        raise TypeError("Text to redact must be a string")

    redacted = text
    detected: list[str] = []
    total_count = 0

    for data_type, placeholder, pattern in _PATTERNS:
        if data_type == "card":
            redacted, count = pattern.subn(
                lambda match, replacement=placeholder: (
                    f"{match.group('label')}{match.group('separator')}{replacement}"
                    if match.group("label")
                    else replacement
                ),
                redacted,
            )
        elif data_type in {"auth_code", "password", "account"}:
            redacted, count = pattern.subn(
                lambda match, replacement=placeholder: (
                    f"{match.group('label')}{match.group('separator')}{replacement}"
                ),
                redacted,
            )
        else:
            redacted, count = pattern.subn(placeholder, redacted)
        if count:
            detected.append(data_type)
            total_count += count

    return RedactionResult(
        text=redacted,
        detected_types=tuple(detected),
        redaction_count=total_count,
    )
