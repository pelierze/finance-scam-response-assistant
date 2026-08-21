from app import (
    clarification_answer_summary,
    completed_clarification_actions,
    level_zero_explanation,
    no_immediate_guide_message,
    privacy_notice_text,
    status_summary,
)
from src.models import (
    TRACKED_ACTIONS,
    ActionObservation,
    ActionStatus,
    StructuredAnalysis,
)


def analysis(**statuses: ActionStatus) -> StructuredAnalysis:
    actions = {
        action: ActionObservation(ActionStatus.NOT_MENTIONED)
        for action in TRACKED_ACTIONS
    }
    for action, status in statuses.items():
        actions[action] = ActionObservation(
            status,
            "테스트 근거" if status is ActionStatus.DONE else None,
        )
    return StructuredAnalysis(None, (), actions)


def test_status_summary_uses_fixed_semantic_colors() -> None:
    summary = status_summary(
        analysis(
            app_installed=ActionStatus.DONE,
            personal_info_shared=ActionStatus.DONE,
        )
    )
    assert summary == (
        ("기기 노출", "위험", "danger"),
        ("개인정보 노출", "확인됨", "caution"),
        ("인증정보 노출", "언급 없음", "info"),
        ("금전 피해", "언급 없음", "info"),
    )


def test_financial_loss_is_always_immediate_red() -> None:
    summary = status_summary(
        analysis(money_transferred=ActionStatus.DONE)
    )
    assert summary[-1] == ("금전 피해", "발생", "danger")


def test_privacy_notice_names_types_without_echoing_values() -> None:
    notice = privacy_notice_text(("resident_id", "account"))

    assert notice is not None
    assert "주민등록번호" in notice
    assert "계좌번호" in notice
    assert "외부 AI 전송 전에" in notice
    assert "900101-1234567" not in notice


def test_follow_up_guides_do_not_claim_there_is_no_response() -> None:
    message = no_immediate_guide_message(has_follow_up_guides=True)

    assert "확인된 노출" in message
    assert "긴급 행동이 없습니다" not in message


def test_status_summary_distinguishes_denied_unknown_and_unmentioned() -> None:
    summary = status_summary(
        analysis(
            app_installed=ActionStatus.UNKNOWN,
            personal_info_shared=ActionStatus.DENIED,
        )
    )

    assert summary[0] == ("기기 노출", "추가 확인 필요", "caution")
    assert summary[1] == ("개인정보 노출", "사용자가 아니오로 확인", "info")
    assert summary[2] == ("인증정보 노출", "언급 없음", "info")


def test_clarification_answer_summary_keeps_actual_user_answers() -> None:
    rows = clarification_answer_summary(
        {
            "personal_info_shared": "denied",
            "app_installed": "unknown",
        }
    )

    assert rows == (
        ("앱 설치 여부", "잘 모르겠음"),
        ("개인정보 전달 여부", "아니오"),
    )


def test_unknown_answer_marks_question_complete_for_current_analysis() -> None:
    completed = completed_clarification_actions(
        set(), {"personal_info_shared": ActionStatus.UNKNOWN}
    )

    assert completed == ("personal_info_shared",)


def test_level_zero_explains_redaction_without_assuming_sharing() -> None:
    message = level_zero_explanation(
        analysis(personal_info_shared=ActionStatus.UNKNOWN),
        ("resident_id",),
    )

    assert "피해 행동은 확인되지 않았습니다" in message
    assert "주민등록번호는 자동 마스킹" in message
    assert "상대방에게 전달된 것으로 판단하지 않습니다" in message
