"""Detect and focus a scam narrative on an explicitly selected person."""

from __future__ import annotations

import re

SELF_SUBJECT = "입력자 본인"
SUBJECT_ALIASES: dict[str, tuple[str, ...]] = {
    "어머니": ("어머니", "엄마"),
    "아버지": ("아버지", "아빠"),
    "배우자": ("배우자", "남편", "아내"),
    "자녀": ("아들", "딸", "자녀"),
    "형제자매": ("형", "누나", "언니", "오빠", "동생"),
    "친구": ("친구",),
    "동료": ("동료",),
}
ALLOWED_SUBJECTS = frozenset({SELF_SUBJECT, *SUBJECT_ALIASES})

_SELF_PATTERN = re.compile(r"(?:저|저는|제가|나는|내가)(?:는|가)?")


def _subject_pattern(aliases: tuple[str, ...]) -> re.Pattern[str]:
    values = "|".join(re.escape(alias) for alias in aliases)
    return re.compile(rf"(?:(?:제|우리)\s*)?(?:{values})(?:가|이|는|은|께서)")


_SUBJECT_PATTERNS = {
    label: _subject_pattern(aliases) for label, aliases in SUBJECT_ALIASES.items()
}


def validate_subject(subject_label: str) -> str:
    """Allow only labels owned by this application, never arbitrary prompt text."""

    if subject_label not in ALLOWED_SUBJECTS:
        raise ValueError("Unsupported analysis subject")
    return subject_label


def detect_analysis_subjects(text: str) -> tuple[str, ...]:
    """Return the self subject followed by explicitly mentioned people."""

    if not isinstance(text, str):
        return (SELF_SUBJECT,)
    detected = [
        label for label, pattern in _SUBJECT_PATTERNS.items() if pattern.search(text)
    ]
    return (SELF_SUBJECT, *detected)


def _subject_mentions(sentence: str) -> tuple[tuple[int, str], ...]:
    """Return every explicit person marker in reading order."""

    matches: list[tuple[int, str]] = [
        (match.start(), SELF_SUBJECT) for match in _SELF_PATTERN.finditer(sentence)
    ]
    for label, pattern in _SUBJECT_PATTERNS.items():
        matches.extend((match.start(), label) for match in pattern.finditer(sentence))
    return tuple(sorted(matches))


def focus_text_on_subject(text: str, subject_label: str) -> str:
    """Keep the selected person's clauses and normalize them to first person."""

    validate_subject(subject_label)
    if subject_label == SELF_SUBJECT:
        return text

    sentences = [
        part.strip() for part in re.split(r"(?<=[.!?])|\n", text) if part.strip()
    ]
    active_subject: str | None = None
    selected: list[str] = []
    for sentence in sentences:
        mentions = _subject_mentions(sentence)
        if not mentions:
            if active_subject == subject_label:
                selected.append(sentence)
            continue

        for index, (start, mentioned_subject) in enumerate(mentions):
            segment_start = 0 if index == 0 else start
            segment_end = (
                mentions[index + 1][0] if index + 1 < len(mentions) else len(sentence)
            )
            if mentioned_subject == subject_label:
                selected.append(sentence[segment_start:segment_end].strip())
        active_subject = mentions[-1][1]

    if not selected:
        return text

    focused = " ".join(selected)
    target_pattern = _SUBJECT_PATTERNS[subject_label]
    return target_pattern.sub("제가", focused)


def subject_question(prompt: str, subject_label: str) -> str:
    """Make safety questions explicit when the affected person is not the user."""

    validate_subject(subject_label)
    if subject_label == SELF_SUBJECT:
        return prompt
    if prompt.startswith("상대방에게"):
        return f"{subject_label}가 {prompt}"
    if prompt.startswith("입력하신"):
        return prompt.replace("입력하신", f"{subject_label}의", 1)
    return f"{subject_label}가 {prompt}"
