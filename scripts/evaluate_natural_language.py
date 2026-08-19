"""Evaluate the local or OpenAI extractor against the labeled dataset."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.analyzer import OpenAIStructuredExtractor
from src.evaluation_service import evaluate_extractor, load_evaluation_cases
from src.local_extractor import LocalKoreanRuleExtractor

ROOT = Path(__file__).parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", choices=("local", "openai"), default="local")
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "data" / "evaluation_cases.json"
    )
    args = parser.parse_args()
    if args.extractor == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            parser.error("OPENAI_API_KEY is required for --extractor openai")
        extractor = OpenAIStructuredExtractor(api_key=api_key)
    else:
        extractor = LocalKoreanRuleExtractor()
    report = evaluate_extractor(load_evaluation_cases(args.dataset), extractor)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
