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
        "personal_info_shared", "개인정보나 신분증 사진을 전달했나요?", 60
    ),
    "link_clicked": ClarificationQuestion(
        "link_clicked", "문자나 메신저의 링크를 실제로 눌렀나요?", 70
    ),
}


def select_questions(
    analysis: StructuredAnalysis, *, limit: int = 3
) -> tuple[ClarificationQuestion, ...]:
    """Return the most urgent unanswered questions without overwhelming users."""

    if limit < 1:
        raise ValueError("Question limit must be at least one")

    candidates: set[str] = {
        action
        for action, observation in analysis.actions.items()
        if action in QUESTION_CATALOG
        and observation.status in {ActionStatus.REQUESTED, ActionStatus.UNKNOWN}
    }

    done = {
        action
        for action, observation in analysis.actions.items()
        if observation.status is ActionStatus.DONE
    }
    not_mentioned = {
        action
        for action, observation in analysis.actions.items()
        if observation.status is ActionStatus.NOT_MENTIONED
    }

    if "link_clicked" in done:
        candidates.update(
            {"app_installed", "remote_control_enabled"} & not_mentioned
        )
    if done & {"app_installed", "remote_control_enabled"}:
        candidates.update(
            {
                "personal_info_shared",
                "financial_info_shared",
                "auth_secret_shared",
            }
            & not_mentioned
        )
    if done and "money_transferred" in not_mentioned:
        candidates.add("money_transferred")

    ordered = sorted(
        (QUESTION_CATALOG[action] for action in candidates),
        key=lambda question: question.priority,
    )
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
