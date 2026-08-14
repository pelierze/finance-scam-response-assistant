import unittest

from src.privacy_filter import redact_sensitive_text


class PrivacyFilterTests(unittest.TestCase):
    def test_redacts_multiple_sensitive_values(self) -> None:
        original = (
            "주민번호 900101-1234567, 전화 010-1234-5678, "
            "이메일 victim@example.com을 알려줬어요."
        )

        result = redact_sensitive_text(original)

        self.assertNotIn("900101-1234567", result.text)
        self.assertNotIn("010-1234-5678", result.text)
        self.assertNotIn("victim@example.com", result.text)
        self.assertEqual(
            set(result.detected_types),
            {"resident_id", "phone", "email"},
        )

    def test_redacts_card_number(self) -> None:
        result = redact_sensitive_text("카드는 1234-5678-9012-3456입니다.")

        self.assertEqual(result.text, "카드는 [카드번호 마스킹]입니다.")
        self.assertIn("card", result.detected_types)

    def test_preserves_context_while_redacting_account_and_auth_code(self) -> None:
        result = redact_sensitive_text(
            "계좌번호는 123-456-789012이고 인증번호 839201을 알려줬어요."
        )

        self.assertIn("계좌번호는 [계좌번호 마스킹]", result.text)
        self.assertIn("인증번호 [인증정보 마스킹]", result.text)
        self.assertNotIn("123-456-789012", result.text)
        self.assertNotIn("839201", result.text)
        self.assertEqual(set(result.detected_types), {"account", "auth_secret"})

    def test_does_not_mask_unrelated_amount(self) -> None:
        result = redact_sensitive_text("안전계좌로 10000000원을 송금했습니다.")

        self.assertEqual(result.text, "안전계좌로 10000000원을 송금했습니다.")
        self.assertFalse(result.was_redacted)

    def test_rejects_non_string_input(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a string"):
            redact_sensitive_text(None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
