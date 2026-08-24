"""Compare case-level local and LLM feedback evaluation outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("local_report", type=Path)
    parser.add_argument("llm_report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    local = json.loads(args.local_report.read_text(encoding="utf-8"))
    llm = json.loads(args.llm_report.read_text(encoding="utf-8"))
    local_results = {item["id"]: item for item in local["results"]}
    llm_results = {item["id"]: item for item in llm["results"]}
    if set(local_results) != set(llm_results):
        raise ValueError("Local and LLM reports must contain the same case IDs")

    fields = ("actions", "active_dimensions", "level", "questions", "guide_ids")
    differences = []
    for case_id in sorted(local_results):
        changed = {
            field: {
                "local": local_results[case_id][field],
                "llm": llm_results[case_id][field],
            }
            for field in fields
            if local_results[case_id][field] != llm_results[case_id][field]
        }
        if changed:
            differences.append({"id": case_id, "differences": changed})

    comparison = {
        "local_metrics": local["metrics"],
        "llm_metrics": llm["metrics"],
        "different_case_count": len(differences),
        "case_differences": differences,
    }
    serialized = json.dumps(comparison, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
