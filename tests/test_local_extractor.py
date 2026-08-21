from src.analyzer import analyze_text
from src.local_extractor import LocalKoreanRuleExtractor
from src.models import ActionStatus
from src.question_engine import select_questions
from src.rule_engine import assess_exposure


def analyze(text: str):
    result = analyze_text(text, LocalKoreanRuleExtractor())
    assert not result.used_fallback
    return result.analysis


def test_denied_installation_is_not_misclassified_as_done() -> None:
    analysis = analyze("앱을 설치하라고 했지만 설치하지 않았습니다.")

    assert analysis.actions["app_installed"].status is ActionStatus.DENIED
    assert not assess_exposure(analysis).device


def test_install_request_is_distinct_from_completed_installation() -> None:
    analysis = analyze("검찰이라는 사람이 앱을 설치하라고 요구했습니다.")

    assert analysis.actions["app_installed"].status is ActionStatus.REQUESTED


def test_compound_sentence_preserves_every_completed_harm() -> None:
    analysis = analyze(
        "검찰이라는 사람의 안내로 앱을 설치하고 주민등록정보를 알려준 뒤 "
        "안전계좌로 돈을 송금했습니다."
    )

    assert analysis.actions["app_installed"].status is ActionStatus.DONE
    assert analysis.actions["personal_info_shared"].status is ActionStatus.DONE
    assert analysis.actions["money_transferred"].status is ActionStatus.DONE
    assessment = assess_exposure(analysis)
    assert assessment.harm_dimensions == frozenset(
        {"device", "personal_data", "financial_loss"}
    )


def test_ambiguous_installation_remains_unknown() -> None:
    analysis = analyze("앱을 설치하라고 해서 확인해 봤는데 뭔가 이상합니다.")

    assert analysis.actions["app_installed"].status is ActionStatus.REQUESTED


def test_sensitive_values_are_redacted_before_local_extraction() -> None:
    result = analyze_text(
        "주민번호 900101-1234567과 계좌번호 123-456-789012를 알려줬습니다.",
        LocalKoreanRuleExtractor(),
    )

    assert set(result.redacted_types) == {"resident_id", "account"}
    assert result.analysis.actions["personal_info_shared"].status is ActionStatus.DONE
    assert result.analysis.actions["financial_info_shared"].status is ActionStatus.DONE


def test_completed_app_installation_and_transfer_do_not_need_clarification() -> None:
    result = analyze_text(
        "전화가 와서 앱 설치를 하고 송금까지 했어요",
        LocalKoreanRuleExtractor(),
    )

    assert result.analysis.actions["suspicious_contact_received"].status is ActionStatus.DONE
    assert result.analysis.actions["app_installed"].status is ActionStatus.DONE
    assert result.analysis.actions["money_transferred"].status is ActionStatus.DONE
    assert select_questions(result.analysis) == ()
