"""Load transparent, deterministic sample scenarios for MVP demonstrations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.models import TRACKED_ACTIONS, StructuredAnalysis


@dataclass(frozen=True)
class SampleCase:
    id: str
    label: str
    text: str
    analysis: StructuredAnalysis
    expected_level: int
    required_guide_ids: frozenset[str]


def load_samples(path: str | Path) -> tuple[SampleCase, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    samples = []
    for item in raw:
        specified = item["actions"]
        actions = {
            action: {
                "status": specified.get(action, "not_mentioned"),
                "evidence": item["text"] if specified.get(action) == "done" else None,
            }
            for action in TRACKED_ACTIONS
        }
        samples.append(
            SampleCase(
                id=item["id"],
                label=item["label"],
                text=item["text"],
                analysis=StructuredAnalysis.from_dict(
                    {
                        "impersonated_entity": None,
                        "risk_signals": item["risk_signals"],
                        "actions": actions,
                    }
                ),
                expected_level=item["expected_level"],
                required_guide_ids=frozenset(item["required_guide_ids"]),
            )
        )
    if len({sample.id for sample in samples}) != len(samples):
        raise ValueError("Sample IDs must be unique")
    return tuple(samples)
