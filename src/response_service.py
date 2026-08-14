"""Load verified guidance and compose actions for confirmed exposures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.models import ExposureAssessment

PRIORITY_ORDER = {"IMMEDIATE": 0, "NEXT": 1, "EVIDENCE": 2, "PREVENTION": 3}


@dataclass(frozen=True)
class ResponseGuide:
    action_id: str
    title: str
    instruction: str
    applies_when: frozenset[str]
    priority: str
    source_title: str
    source_url: str
    issuing_authority: str
    verified_at: date

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ResponseGuide:
        required = {
            "action_id", "title", "instruction", "applies_when", "priority",
            "source_title", "source_url", "issuing_authority", "verified_at",
        }
        if set(value) != required:
            raise ValueError("Guide fields do not match the required schema")
        if value["priority"] not in PRIORITY_ORDER:
            raise ValueError(f"Invalid guide priority: {value['priority']!r}")
        parsed_url = urlparse(value["source_url"])
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise ValueError("Guide source must be an absolute HTTPS URL")
        applies_when = value["applies_when"]
        if not isinstance(applies_when, list) or not applies_when:
            raise ValueError("Guide must have at least one application condition")
        text_fields = required - {"applies_when", "verified_at"}
        if any(not isinstance(value[field], str) or not value[field].strip() for field in text_fields):
            raise ValueError("Guide text fields must be non-empty strings")
        return cls(
            action_id=value["action_id"], title=value["title"],
            instruction=value["instruction"], applies_when=frozenset(applies_when),
            priority=value["priority"], source_title=value["source_title"],
            source_url=value["source_url"], issuing_authority=value["issuing_authority"],
            verified_at=date.fromisoformat(value["verified_at"]),
        )


def load_guides(path: str | Path) -> tuple[ResponseGuide, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Guide store must be a non-empty list")
    guides = tuple(ResponseGuide.from_dict(item) for item in raw)
    ids = [guide.action_id for guide in guides]
    if len(ids) != len(set(ids)):
        raise ValueError("Guide action IDs must be unique")
    return guides


def compose_guides(
    assessment: ExposureAssessment, guides: tuple[ResponseGuide, ...]
) -> tuple[ResponseGuide, ...]:
    confirmed = assessment.confirmed_exposures
    selected = [guide for guide in guides if guide.applies_when & confirmed]
    return tuple(sorted(selected, key=lambda guide: (PRIORITY_ORDER[guide.priority], guide.action_id)))
