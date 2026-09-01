"""Build reproducibility metadata for local and provider-backed evaluations."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from src.analyzer import SYSTEM_PROMPT, LLMAnalysisSchema

SCHEMA_VERSION = "LLMAnalysisSchema-v1"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Unsupported metadata value: {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def build_evaluation_metadata(
    *,
    extractor: str,
    model: str | None,
    temperature: float | None,
    max_attempts: int,
    cases: list[dict[str, Any]],
    guide_labels: dict[str, Any],
    started_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = started_at or datetime.now(UTC)
    try:
        openai_sdk_version = version("openai") if extractor == "openai" else None
    except PackageNotFoundError:
        openai_sdk_version = None
    return {
        "started_at": timestamp.astimezone(UTC).isoformat(),
        "extractor": extractor,
        "provider": "openai" if extractor == "openai" else "local",
        "api_path": "responses.parse" if extractor == "openai" else None,
        "model": model,
        "temperature": temperature,
        "max_attempts": max_attempts,
        "schema_version": SCHEMA_VERSION,
        "system_prompt_sha256": _sha256(SYSTEM_PROMPT),
        "schema_sha256": _sha256(
            _canonical_json(LLMAnalysisSchema.model_json_schema())
        ),
        "case_set_sha256": _sha256(_canonical_json(cases)),
        "case_count": len(cases),
        "guide_labels_sha256": _sha256(_canonical_json(guide_labels)),
        "guide_label_case_count": len(guide_labels),
        "openai_sdk_version": openai_sdk_version,
    }
