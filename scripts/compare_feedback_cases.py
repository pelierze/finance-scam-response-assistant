"""Compare reviewed feedback cases between a Git baseline and current code."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
DEFAULT_GLOB = "data/feedback/reviewed/context-cases-*.jsonl"
SOURCE_FILES = (
    "src/__init__.py",
    "src/local_extractor.py",
    "src/models.py",
    "src/privacy_filter.py",
    "src/question_engine.py",
    "src/rule_engine.py",
)
CHILD_PROGRAM = r"""
import json
import sys

from src.local_extractor import LocalKoreanRuleExtractor
from src.models import StructuredAnalysis
from src.privacy_filter import redact_sensitive_text
from src.question_engine import select_questions
from src.rule_engine import assess_exposure

cases = json.load(sys.stdin)
extractor = LocalKoreanRuleExtractor()
results = []
for case in cases:
    redaction = redact_sensitive_text(case["input"])
    analysis = StructuredAnalysis.from_dict(extractor.extract(redaction.text))
    assessment = assess_exposure(analysis)
    results.append(
        {
            "id": case["id"],
            "actions": {
                action: observation.status.value
                for action, observation in analysis.actions.items()
            },
            "evidence": {
                action: observation.evidence
                for action, observation in analysis.actions.items()
            },
            "questions": [
                question.action for question in select_questions(analysis)
            ],
            "confirmed_exposures": sorted(assessment.confirmed_exposures),
            "active_dimensions": sorted(assessment.active_dimensions),
            "level": int(assessment.representative_level),
            "redacted_types": sorted(redaction.detected_types),
        }
    )
json.dump(results, sys.stdout, ensure_ascii=False)
"""


@dataclass(frozen=True)
class Comparison:
    case: dict[str, Any]
    baseline: dict[str, Any]
    current: dict[str, Any]

    @staticmethod
    def matches_expected(case: dict[str, Any], result: dict[str, Any]) -> bool:
        expected_actions = case["expected_actions"]
        if any(
            result["actions"][action] != status
            for action, status in expected_actions.items()
        ):
            return False
        for action, fragments in case.get("expected_evidence_contains", {}).items():
            evidence = result.get("evidence", {}).get(action) or ""
            if any(fragment not in evidence for fragment in fragments):
                return False
        expected_exposures = set(case.get("expected_exposures", []))
        forbidden_exposures = set(case.get("forbidden_exposures", []))
        actual_exposures = set(result["active_dimensions"])
        expected_questions = set(case.get("expected_questions", []))
        forbidden_questions = set(case.get("forbidden_questions", []))
        actual_questions = set(result["questions"])
        expected_redactions = set(case.get("expected_redacted_types", []))
        forbidden_redactions = set(case.get("forbidden_redacted_types", []))
        actual_redactions = set(result["redacted_types"])
        return (
            expected_exposures <= actual_exposures
            and not forbidden_exposures & actual_exposures
            and expected_questions <= actual_questions
            and not forbidden_questions & actual_questions
            and expected_redactions <= actual_redactions
            and not forbidden_redactions & actual_redactions
            and (
                "expected_level" not in case
                or result["level"] == case["expected_level"]
            )
        )

    @property
    def baseline_passed(self) -> bool:
        return self.matches_expected(self.case, self.baseline)

    @property
    def current_passed(self) -> bool:
        return self.matches_expected(self.case, self.current)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-glob", default=DEFAULT_GLOB)
    parser.add_argument("--baseline-ref", default="origin/main")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def load_cases(pattern: str) -> list[dict[str, Any]]:
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
        raise ValueError("Feedback case IDs must be unique across files")
    required = {"id", "input", "expected_actions"}
    if any(not required <= set(case) for case in cases):
        raise ValueError("Feedback cases must include the required fields")
    return cases


def materialize_ref(ref: str, destination: Path) -> None:
    for relative_path in SOURCE_FILES:
        content = subprocess.run(
            ["git", "show", f"{ref}:{relative_path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def evaluate(source_root: Path, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source_root)
    completed = subprocess.run(
        [sys.executable, "-c", CHILD_PROGRAM],
        cwd=source_root,
        env=environment,
        input=json.dumps(cases, ensure_ascii=False),
        text=True,
        check=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def compact_states(case: dict[str, Any], result: dict[str, Any]) -> str:
    return ", ".join(
        f"{action}={result['actions'][action]}" for action in case["expected_actions"]
    )


def markdown_report(comparisons: list[Comparison], baseline_ref: str) -> str:
    baseline_passed = sum(item.baseline_passed for item in comparisons)
    current_passed = sum(item.current_passed for item in comparisons)
    lines = [
        "# 피드백 사례 전후 비교",
        "",
        f"- 기준 코드: `{baseline_ref}`",
        "- 수정 코드: 현재 작업 트리",
        f"- 전체 사례: {len(comparisons)}건",
        f"- 기준 코드 통과: {baseline_passed}/{len(comparisons)}",
        f"- 수정 코드 통과: {current_passed}/{len(comparisons)}",
        "",
        "| CASE | 기준 코드 | 수정 코드 | 기대 상태 | 기준 | 수정 |",
        "|---|---|---|---|---:|---:|",
    ]
    for item in comparisons:
        expected = ", ".join(
            f"{action}={status}"
            for action, status in item.case["expected_actions"].items()
        )
        lines.append(
            "| {id} | {baseline} | {current} | {expected} | {baseline_pass} | "
            "{current_pass} |".format(
                id=item.case["id"],
                baseline=compact_states(item.case, item.baseline),
                current=compact_states(item.case, item.current),
                expected=expected,
                baseline_pass="O" if item.baseline_passed else "X",
                current_pass="O" if item.current_passed else "X",
            )
        )
    lines.extend(
        [
            "",
            "## 판정 기준",
            "",
            (
                "각 사례는 기대 행동 상태, 추가 질문 목록과 `done` 행동으로부터 "
                "계산한 활성 노출 집합이 모두 일치해야 통과한다."
            ),
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases_glob)
    with tempfile.TemporaryDirectory(prefix="feedback-baseline-") as directory:
        baseline_root = Path(directory)
        materialize_ref(args.baseline_ref, baseline_root)
        baseline_results = evaluate(baseline_root, cases)
    current_results = evaluate(ROOT, cases)
    comparisons = [
        Comparison(case, baseline, current)
        for case, baseline, current in zip(
            cases, baseline_results, current_results, strict=True
        )
    ]
    if args.format == "json":
        print(
            json.dumps(
                [
                    {
                        "case": item.case,
                        "baseline": item.baseline,
                        "current": item.current,
                        "baseline_passed": item.baseline_passed,
                        "current_passed": item.current_passed,
                    }
                    for item in comparisons
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(markdown_report(comparisons, args.baseline_ref))


if __name__ == "__main__":
    main()
