import unittest

from src.models import (
    TRACKED_ACTIONS,
    ActionObservation,
    ActionStatus,
    StructuredAnalysis,
)
from src.question_engine import QUESTION_CATALOG, apply_answers, select_questions


def analysis_with(**statuses: ActionStatus) -> StructuredAnalysis:
    actions = {
        name: ActionObservation(ActionStatus.NOT_MENTIONED) for name in TRACKED_ACTIONS
    }
    for name, status in statuses.items():
        evidence = "테스트 근거" if status is ActionStatus.DONE else None
        actions[name] = ActionObservation(status, evidence)
    return StructuredAnalysis(None, (), actions)


class QuestionEngineTests(unittest.TestCase):
    def test_personal_information_question_distinguishes_input_from_sharing(self) -> None:
        question = QUESTION_CATALOG["personal_info_shared"]

        self.assertEqual(
            question.prompt,
            "입력하신 개인정보를 상대방에게 실제로 전달했나요?",
        )

    def test_prioritizes_money_and_device_uncertainty(self) -> None:
        questions = select_questions(
            analysis_with(
                app_installed=ActionStatus.UNKNOWN,
                money_transferred=ActionStatus.REQUESTED,
                link_clicked=ActionStatus.UNKNOWN,
            ),
            limit=2,
        )
        self.assertEqual(
            [question.action for question in questions],
            ["money_transferred", "app_installed"],
        )

    def test_link_click_triggers_adaptive_device_questions(self) -> None:
        questions = select_questions(analysis_with(link_clicked=ActionStatus.DONE))
        actions = {question.action for question in questions}
        self.assertEqual(
            actions,
            {"money_transferred", "remote_control_enabled", "app_installed"},
        )

    def test_applies_explicit_answer_without_mutating_original(self) -> None:
        original = analysis_with(app_installed=ActionStatus.UNKNOWN)
        updated = apply_answers(original, {"app_installed": ActionStatus.DONE})
        self.assertEqual(original.actions["app_installed"].status, ActionStatus.UNKNOWN)
        self.assertEqual(updated.actions["app_installed"].status, ActionStatus.DONE)
        self.assertEqual(updated.actions["app_installed"].evidence, "사용자 확인 응답")

    def test_rejects_requested_as_user_answer(self) -> None:
        with self.assertRaisesRegex(ValueError, "done, denied, or unknown"):
            apply_answers(
                analysis_with(), {"app_installed": ActionStatus.REQUESTED}
            )

    def test_rejects_zero_question_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            select_questions(analysis_with(), limit=0)


if __name__ == "__main__":
    unittest.main()
