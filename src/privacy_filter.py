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
        re.compile(
            r"(?<!\d)(?:"
            r"01[016789]\d{7,8}|"
            r"01[016789][- ]\d{3,4}[- ]\d{4}|"
            r"\(01[016789]\)\s*\d{3,4}[- ]\d{4}"
            r")(?!\d)"
        ),
    ),
    (
        "card",
        "[카드번호 마스킹]",
        re.compile(
            r"(?:(?P<label>카드번호|카드)"
            r"(?P<separator>\s*(?:는|은|가|를|:)?\s*)"
            r"(?P<value>\d{16})(?!\d))|"
            r"(?P<formatted>(?<!주문번호 )(?<!주문번호는 )"
            r"(?<!\d)(?:\d{4}[- ]){3}\d{4}(?!\d))"
        ),
    ),
    (
        "auth_code",
        "[인증정보 마스킹]",
        re.compile(
            r"(?P<label>인증번호|인증코드|보안코드|OTP\s*번호)"
            r"(?P<separator>\s*(?:는|은|가|:)?\s*)"
            r"(?P<value>[A-Za-z0-9!@#$%^&*]{4,20})",
            re.IGNORECASE,
        ),
    ),
    (
        "password",
        "[비밀번호 마스킹]",
        re.compile(
            r"(?P<label>비밀번호|비번)"
            r"(?P<separator>\s*(?:는|은|가|이|:)?\s*)"
            r"(?P<value>[A-Za-z0-9_!@#$%^&*]{4,20})",
            re.IGNORECASE,
        ),
    ),
    (
        "account",
        "[계좌번호 마스킹]",
        re.compile(
            r"(?:(?P<label>계좌번호|계좌)"
            r"(?P<separator>\s*(?:는|은|가|:)?\s*)"
            r"(?P<value>\d(?:[- ]?\d){9,13}))|"
            r"(?:(?P<bank>"
            r"[가-힣A-Za-z]{1,20}(?:은행|뱅크)|"
            r"(?:[A-Za-z]{1,5})?(?:농협|수협|신협|새마을금고)|"
            r"우체국(?:예금)?|KB국민|신한|IBK"
            r")(?P<bank_separator>\s+)"
            r"(?!01[016789](?:[- ]?\d){7,8}(?!\d))"
            r"(?P<bank_value>\d(?:[- ]?\d){9,13})(?=\s*(?:계좌|(?:으)?로)))",
            re.IGNORECASE,
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

    # Account labels provide stronger context than a bare 13-digit resident-ID
    # shape. Process them first so compact account numbers such as
    # ``3011234567891`` are not consumed by the resident-ID rule.
    ordered_patterns = sorted(_PATTERNS, key=lambda item: item[0] != "account")
    for data_type, placeholder, pattern in ordered_patterns:
        if data_type == "card":
            redacted, count = pattern.subn(
                lambda match, replacement=placeholder: (
                    f"{match.group('label')}{match.group('separator')}{replacement}"
                    if match.group("label")
                    else replacement
                ),
                redacted,
            )
        elif data_type in {"auth_code", "password"}:
            repeated_values = (
                [match.group("value") for match in pattern.finditer(redacted)]
                if data_type == "auth_code"
                else []
            )
            redacted, count = pattern.subn(
                lambda match, replacement=placeholder: (
                    f"{match.group('label')}{match.group('separator')}{replacement}"
                ),
                redacted,
            )
            if data_type == "auth_code":
                for value in dict.fromkeys(repeated_values):
                    repeated_pattern = re.compile(
                        rf"(?P<label>(?:첫\s*번째|두\s*번째)도\s*){re.escape(value)}"
                    )
                    redacted, repeated_count = repeated_pattern.subn(
                        lambda match, replacement=placeholder: (
                            f"{match.group('label')}{replacement}"
                        ),
                        redacted,
                    )
                    count += repeated_count
        elif data_type == "account":
            redacted, count = pattern.subn(
                lambda match, replacement=placeholder: (
                    f"{match.group('label')}{match.group('separator')}{replacement}"
                    if match.group("label")
                    else (
                        f"{match.group('bank')}{match.group('bank_separator')}"
                        f"{replacement}"
                    )
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
