import unittest

from src.models import (
    TRACKED_ACTIONS,
    ActionObservation,
    ActionStatus,
    StructuredAnalysis,
)


def valid_payload() -> dict:
    return {
        "impersonated_entity": "검찰",
        "risk_signals": ["수사기관 사칭", "앱 설치 요구"],
        "actions": {
            name: {"status": "not_mentioned", "evidence": None}
            for name in TRACKED_ACTIONS
        },
    }


class ActionObservationTests(unittest.TestCase):
    def test_completed_action_requires_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "must include evidence"):
            ActionObservation(status=ActionStatus.DONE)

    def test_rejects_unknown_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid action status"):
            ActionObservation.from_dict({"status": "maybe", "evidence": None})


class StructuredAnalysisTests(unittest.TestCase):
    def test_builds_valid_analysis_and_deduplicates_signals(self) -> None:
        payload = valid_payload()
        payload["risk_signals"].append("수사기관 사칭")
        payload["actions"]["app_installed"] = {
            "status": "requested",
            "evidence": "앱을 설치하라고 했습니다",
        }

        analysis = StructuredAnalysis.from_dict(payload)

        self.assertEqual(analysis.impersonated_entity, "검찰")
        self.assertEqual(analysis.risk_signals, ("수사기관 사칭", "앱 설치 요구"))
        self.assertEqual(
            analysis.actions["app_installed"].status,
            ActionStatus.REQUESTED,
        )

    def test_rejects_missing_action_key(self) -> None:
        payload = valid_payload()
        del payload["actions"]["money_transferred"]

        with self.assertRaisesRegex(ValueError, "missing=.*money_transferred"):
            StructuredAnalysis.from_dict(payload)

    def test_rejects_unexpected_top_level_field(self) -> None:
        payload = valid_payload()
        payload["generated_advice"] = "임의 행동 지침"

        with self.assertRaisesRegex(ValueError, "extra=.*generated_advice"):
            StructuredAnalysis.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
