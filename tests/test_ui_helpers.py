from types import SimpleNamespace

from app import status_summary


def assessment(**overrides):
    values = {
        "device": frozenset(),
        "personal_data": frozenset(),
        "financial_data": frozenset(),
        "authentication": frozenset(),
        "financial_loss": frozenset(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_status_summary_uses_fixed_semantic_colors() -> None:
    summary = status_summary(
        assessment(
            device=frozenset({"app_installed"}),
            personal_data=frozenset({"personal_info_shared"}),
        )
    )
    assert summary == (
        ("기기 노출", "위험", "danger"),
        ("개인정보 노출", "확인됨", "caution"),
        ("인증정보 노출", "확인 안 됨", "info"),
        ("금전 피해", "확인 안 됨", "info"),
    )


def test_financial_loss_is_always_immediate_red() -> None:
    summary = status_summary(
        assessment(financial_loss=frozenset({"money_transferred"}))
    )
    assert summary[-1] == ("금전 피해", "발생", "danger")
