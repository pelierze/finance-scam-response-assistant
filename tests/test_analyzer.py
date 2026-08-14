import unittest

from src.analyzer import analyze_text
from src.models import TRACKED_ACTIONS, ActionStatus


def valid_payload() -> dict:
    return {
        "impersonated_entity": "검찰",
        "risk_signals": ["수사기관 사칭"],
        "actions": {
            action: {"status": "not_mentioned", "evidence": None}
            for action in TRACKED_ACTIONS
        },
    }


class FakeExtractor:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.inputs = []

    def extract(self, text: str) -> dict:
        self.inputs.append(text)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return output


class AnalyzerTests(unittest.TestCase):
    def test_redacts_before_extractor_and_returns_valid_analysis(self) -> None:
        payload = valid_payload()
        payload["actions"]["auth_secret_shared"] = {
            "status": "done",
            "evidence": "인증번호를 알려줬어요",
        }
        extractor = FakeExtractor([payload])

        result = analyze_text("인증번호 839201을 알려줬어요", extractor)

        self.assertNotIn("839201", extractor.inputs[0])
        self.assertIn("auth_secret", result.redacted_types)
        self.assertFalse(result.used_fallback)
        self.assertEqual(
            result.analysis.actions["auth_secret_shared"].status,
            ActionStatus.DONE,
        )

    def test_retries_invalid_output_then_succeeds(self) -> None:
        extractor = FakeExtractor([{"bad": "schema"}, valid_payload()])
        result = analyze_text("검찰이라고 전화가 왔습니다", extractor)
        self.assertEqual(len(extractor.inputs), 2)
        self.assertFalse(result.used_fallback)

    def test_provider_failure_returns_safe_empty_analysis(self) -> None:
        extractor = FakeExtractor([RuntimeError("network"), RuntimeError("network")])
        result = analyze_text("돈을 보냈습니다", extractor)
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.error_code, "provider_unavailable")
        self.assertFalse(result.analysis.actions["money_transferred"].status is ActionStatus.DONE)

    def test_invalid_input_does_not_call_provider(self) -> None:
        extractor = FakeExtractor([])
        result = analyze_text("   ", extractor)
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.error_code, "invalid_input")
        self.assertEqual(extractor.inputs, [])

    def test_rejects_unsafe_retry_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "between one and three"):
            analyze_text("상황", FakeExtractor([]), max_attempts=4)


if __name__ == "__main__":
    unittest.main()
