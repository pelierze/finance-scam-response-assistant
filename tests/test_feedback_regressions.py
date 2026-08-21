import json
from pathlib import Path

from src.analyzer import analyze_text
from src.local_extractor import LocalKoreanRuleExtractor
from src.models import TRACKED_ACTIONS, ActionStatus
from src.question_engine import select_questions
from src.rule_engine import assess_exposure

CASES_DIRECTORY = Path(__file__).parents[1] / "data" / "feedback" / "reviewed"


def load_cases() -> list[dict]:
    return [
        json.loads(line)
        for path in sorted(CASES_DIRECTORY.glob("context-cases-*.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_feedback_cases_are_complete_and_unique() -> None:
    cases = load_cases()

    assert [case["id"] for case in cases] == [
        f"CASE-{number:03d}" for number in range(1, 21)
    ]
    assert len({case["id"] for case in cases}) == 20
    assert all(set(case["expected_actions"]) <= set(TRACKED_ACTIONS) for case in cases)


def test_feedback_cases_match_actions_exposures_questions_levels_and_redaction() -> (
    None
):
    for case in load_cases():
        result = analyze_text(case["input"], LocalKoreanRuleExtractor())
        predicted = result.analysis

        for action, expected_status in case["expected_actions"].items():
            assert predicted.actions[action].status is ActionStatus(expected_status), (
                case["id"],
                action,
                predicted.actions[action].status,
            )
        for action, fragments in case.get("expected_evidence_contains", {}).items():
            evidence = predicted.actions[action].evidence or ""
            assert all(fragment in evidence for fragment in fragments), (
                case["id"],
                action,
                evidence,
            )
        questions = {question.action for question in select_questions(predicted)}
        assert set(case.get("expected_questions", [])) <= questions, case["id"]
        assert not set(case.get("forbidden_questions", [])) & questions, case["id"]
        assessment = assess_exposure(predicted)
        assert set(case.get("expected_exposures", [])) <= set(
            assessment.active_dimensions
        ), case["id"]
        assert not set(case.get("forbidden_exposures", [])) & set(
            assessment.active_dimensions
        ), case["id"]
        if "expected_level" in case:
            assert int(assessment.representative_level) == case["expected_level"], case[
                "id"
            ]
        assert set(case.get("expected_redacted_types", [])) <= set(
            result.redacted_types
        ), case["id"]
        assert not set(case.get("forbidden_redacted_types", [])) & set(
            result.redacted_types
        ), case["id"]
