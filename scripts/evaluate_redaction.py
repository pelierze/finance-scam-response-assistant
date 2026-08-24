"""Print metrics for the synthetic redaction evaluation set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.redaction_evaluation import evaluate_redaction_cases, load_redaction_cases

ROOT = Path(__file__).parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "redaction_evaluation_cases.json",
    )
    args = parser.parse_args()
    report = evaluate_redaction_cases(load_redaction_cases(args.dataset))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
