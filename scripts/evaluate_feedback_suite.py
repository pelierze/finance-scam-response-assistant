"""Evaluate reviewed feedback cases with the local or OpenAI extractor."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from src.analyzer import OpenAIStructuredExtractor
from src.evaluation_metadata import build_evaluation_metadata
from src.feedback_evaluation import (
    load_guide_expectations,
    run_feedback_cases,
    score_feedback_runs,
)
from src.local_extractor import LocalKoreanRuleExtractor
from src.response_service import load_guides

ROOT = Path(__file__).parents[1]
DEFAULT_GLOB = "data/feedback/reviewed/context-cases-*.jsonl"


def load_cases(pattern: str) -> list[dict]:
    paths = sorted(ROOT.glob(pattern))
    if not paths:
        raise ValueError(f"No feedback case files matched: {pattern}")
    cases = [
        json.loads(line)
        for path in paths
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Feedback case IDs must be unique")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", choices=("local", "openai"), default="local")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-attempts", type=int, choices=range(1, 4), default=2)
    parser.add_argument("--cases-glob", default=DEFAULT_GLOB)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument(
        "--guide-labels",
        type=Path,
        default=ROOT / "data" / "guide_evaluation_labels.json",
    )
    args = parser.parse_args()

    if args.extractor == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            parser.error("OPENAI_API_KEY is required for --extractor openai")
        extractor = OpenAIStructuredExtractor(
            api_key=api_key,
            model=args.model,
            temperature=args.temperature,
        )
    else:
        extractor = LocalKoreanRuleExtractor()

    cases = load_cases(args.cases_glob)
    guides = load_guides(ROOT / "data" / "response_guides.json")
    guide_expectations = load_guide_expectations(
        args.guide_labels,
        case_ids={case["id"] for case in cases},
        guide_ids={guide.action_id for guide in guides},
    )
    started_at = datetime.now(UTC)
    runs = run_feedback_cases(
        cases, extractor, guides, max_attempts=args.max_attempts
    )
    report = {
        "metadata": build_evaluation_metadata(
            extractor=args.extractor,
            model=args.model if args.extractor == "openai" else None,
            temperature=args.temperature if args.extractor == "openai" else None,
            max_attempts=args.max_attempts,
            cases=cases,
            guide_labels=guide_expectations,
            started_at=started_at,
        ),
        "extractor": args.extractor,
        "model": args.model if args.extractor == "openai" else None,
        "metrics": score_feedback_runs(
            cases, runs, guides, guide_expectations
        ),
        "results": [run.to_dict() for run in runs],
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    if args.summary_only:
        print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    else:
        print(serialized)


if __name__ == "__main__":
    main()
