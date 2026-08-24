"""Print submission-facing metrics for all synthetic redaction datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.redaction_suite import load_and_evaluate_redaction_suite

ROOT = Path(__file__).parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--general-dataset",
        type=Path,
        default=ROOT / "data" / "redaction_evaluation_cases.json",
    )
    parser.add_argument(
        "--bank-dataset",
        type=Path,
        default=(
            ROOT
            / "data"
            / "feedback"
            / "reviewed"
            / "bank-account-redaction-inputs.txt"
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = load_and_evaluate_redaction_suite(
        args.general_dataset, args.bank_dataset
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
