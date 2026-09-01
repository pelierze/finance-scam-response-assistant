"""Select and apply clarification questions for safety-critical actions."""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.models import ActionObservation, ActionStatus, StructuredAnalysis


@dataclass(frozen=True)
class ClarificationQuestion:
    action: str
    prompt: str
    priority: int


QUESTION_CATALOG = {
    "money_transferred": ClarificationQuestion(
        "money_transferred", "돈을 송금하거나 현금·상품권을 전달했나요?", 10
    ),
    "remote_control_enabled": ClarificationQuestion(
        "remote_control_enabled", "상대방에게 화면 공유나 원격제어를 허용했나요?", 20
    ),
    "app_installed": ClarificationQuestion(
        "app_installed", "상대방이 안내한 앱을 실제로 설치했나요?", 30
    ),
    "auth_secret_shared": ClarificationQuestion(
        "auth_secret_shared", "인증번호·비밀번호·보안매체 정보를 전달했나요?", 40
    ),
    "financial_info_shared": ClarificationQuestion(
        "financial_info_shared", "계좌번호나 카드정보를 전달했나요?", 50
    ),
    "personal_info_shared": ClarificationQuestion(
        "personal_info_shared",
        "입력하신 개인정보를 상대방에게 실제로 전달했나요?",
        60,
    ),
    "link_clicked": ClarificationQuestion(
        "link_clicked", "문자나 메신저의 링크를 실제로 눌렀나요?", 70
    ),
}

SAFETY_SCREENING_ACTIONS = (
    "money_transferred",
    "remote_control_enabled",
    "auth_secret_shared",
)


def select_questions(
    analysis: StructuredAnalysis, *, limit: int = 3
) -> tuple[ClarificationQuestion, ...]:
    """Ask only about explicitly requested or uncertain actions."""

    if limit < 1:
        raise ValueError("Question limit must be at least one")

    candidates: set[str] = {
        action
        for action, observation in analysis.actions.items()
        if action in QUESTION_CATALOG
        and observation.status in {ActionStatus.REQUESTED, ActionStatus.UNKNOWN}
    }

    ordered = sorted(
        (QUESTION_CATALOG[action] for action in candidates),
        key=lambda question: question.priority,
    )
    return tuple(ordered[:limit])


def select_safety_checks(
    analysis: StructuredAnalysis, *, limit: int = 3
) -> tuple[ClarificationQuestion, ...]:
    """Screen high-impact actions that were omitted after a suspicious contact."""

    if limit < 1:
        raise ValueError("Question limit must be at least one")

    contact_status = analysis.actions["suspicious_contact_received"].status
    if contact_status not in {ActionStatus.DONE, ActionStatus.REQUESTED}:
        return ()

    questions = tuple(
        QUESTION_CATALOG[action]
        for action in SAFETY_SCREENING_ACTIONS
        if analysis.actions[action].status is ActionStatus.NOT_MENTIONED
    )
    return questions[:limit]


def select_follow_up_questions(
    analysis: StructuredAnalysis, *, limit: int = 3
) -> tuple[ClarificationQuestion, ...]:
    """Combine extraction clarifications and independent safety screening."""

    if limit < 1:
        raise ValueError("Question limit must be at least one")

    candidates = {
        question.action: question
        for question in (
            *select_questions(analysis, limit=len(QUESTION_CATALOG)),
            *select_safety_checks(analysis, limit=len(SAFETY_SCREENING_ACTIONS)),
        )
    }
    ordered = sorted(candidates.values(), key=lambda question: question.priority)
    return tuple(ordered[:limit])


def apply_answers(
    analysis: StructuredAnalysis, answers: dict[str, ActionStatus]
) -> StructuredAnalysis:
    """Merge explicit user answers, rejecting unsupported or ambiguous values."""

    unsupported = set(answers) - set(QUESTION_CATALOG)
    if unsupported:
        raise ValueError(f"Unsupported answer actions: {sorted(unsupported)}")

    allowed = {ActionStatus.DONE, ActionStatus.DENIED, ActionStatus.UNKNOWN}
    invalid = {action: status for action, status in answers.items() if status not in allowed}
    if invalid:
        raise ValueError("Answers must be done, denied, or unknown")

    updated_actions = dict(analysis.actions)
    for action, status in answers.items():
        evidence = "사용자 확인 응답" if status is ActionStatus.DONE else None
        updated_actions[action] = ActionObservation(status=status, evidence=evidence)

    return replace(analysis, actions=updated_actions)
