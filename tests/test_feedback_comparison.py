import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "compare_feedback_cases.py"
SPEC = importlib.util.spec_from_file_location("compare_feedback_cases", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_feedback_comparison_discovers_all_reviewed_case_files() -> None:
    cases = MODULE.load_cases(MODULE.DEFAULT_GLOB)

    assert [case["id"] for case in cases] == [
        f"CASE-{number:03d}" for number in range(1, 21)
    ]


def test_comparison_requires_states_questions_and_exposures_to_match() -> None:
    case = {
        "id": "CASE-X",
        "input": "앱을 설치했습니다.",
        "expected_actions": {"app_installed": "done"},
        "expected_exposures": ["device"],
        "forbidden_exposures": ["financial_loss"],
        "expected_questions": [],
        "forbidden_questions": ["app_installed"],
        "expected_level": 3,
    }
    matching = {
        "actions": {"app_installed": "done"},
        "questions": [],
        "confirmed_exposures": ["app_installed"],
        "active_dimensions": ["device"],
        "redacted_types": [],
        "level": 3,
    }
    forbidden_question = {**matching, "questions": ["app_installed"]}

    assert MODULE.Comparison.matches_expected(case, matching)
    assert not MODULE.Comparison.matches_expected(case, forbidden_question)
