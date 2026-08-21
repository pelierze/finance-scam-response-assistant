from src.feedback_evaluation import FeedbackRun, score_feedback_runs
from src.response_service import load_guides


def test_feedback_metrics_use_only_explicit_labels(tmp_path) -> None:
    guides = load_guides("data/response_guides.json")
    cases = [
        {
            "id": "CASE-X",
            "input": "앱을 설치했고 돈은 보내지 않았어요.",
            "expected_actions": {
                "app_installed": "done",
                "money_transferred": "denied",
            },
            "expected_exposures": ["device"],
            "forbidden_exposures": ["financial_loss"],
            "expected_questions": [],
            "forbidden_questions": ["app_installed", "money_transferred"],
            "expected_level": 3,
        }
    ]
    actions = {
        action: "not_mentioned"
        for action in (
            "suspicious_contact_received",
            "link_clicked",
            "app_installed",
            "remote_control_enabled",
            "personal_info_shared",
            "financial_info_shared",
            "auth_secret_shared",
            "money_transferred",
        )
    }
    actions.update(app_installed="done", money_transferred="denied")
    runs = [
        FeedbackRun(
            case_id="CASE-X",
            actions=actions,
            active_dimensions=("device",),
            level=3,
            questions=(),
            redacted_types=(),
            guide_ids=("DEVICE_EXPOSURE_01", "AUTH_EXPOSURE_01"),
            used_fallback=False,
            error_code=None,
        )
    ]

    metrics = score_feedback_runs(cases, runs, guides)

    assert metrics["case_pass_rate"] == 1
    assert metrics["action_status_accuracy"] == 1
    assert metrics["action_status_labels"] == 2
    assert metrics["exposure_accuracy"] == 1
    assert metrics["forbidden_question_incidence"] == 0
    assert metrics["high_risk_required_guide_omission_rate"] == 0


def test_fallback_is_never_counted_as_a_passing_case() -> None:
    guides = load_guides("data/response_guides.json")
    case = {"id": "CASE-X", "input": "무관", "expected_actions": {}}
    run = FeedbackRun(
        case_id="CASE-X",
        actions={},
        active_dimensions=(),
        level=0,
        questions=(),
        redacted_types=(),
        guide_ids=(),
        used_fallback=True,
        error_code="provider_unavailable",
    )

    metrics = score_feedback_runs([case], [run], guides)

    assert metrics["case_pass_rate"] == 0
    assert metrics["fallback_cases"] == 1
    assert metrics["failed_cases"][0]["failures"] == [
        "fallback: provider_unavailable"
    ]
