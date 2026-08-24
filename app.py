"""Streamlit MVP for immediate finance-scam response guidance."""

from __future__ import annotations

import os
from html import escape
from pathlib import Path

import streamlit as st

from src.analyzer import OpenAIStructuredExtractor, analyze_text
from src.local_extractor import LocalKoreanRuleExtractor
from src.models import ActionStatus, StructuredAnalysis
from src.question_engine import apply_answers, select_questions
from src.response_service import compose_guides, load_guides
from src.rule_engine import assess_exposure
from src.sample_service import load_samples

ROOT = Path(__file__).parent
LEVEL_NAMES = {
    0: "정보 부족 또는 일반 상담",
    1: "의심 연락·요구 단계",
    2: "링크·웹 노출 단계",
    3: "기기 노출 단계",
    4: "정보·인증수단 노출 단계",
    5: "금전 피해 단계",
}
ANSWER_MAP = {
    "예": ActionStatus.DONE,
    "아니오": ActionStatus.DENIED,
    "잘 모르겠음": ActionStatus.UNKNOWN,
    "해당 없음": ActionStatus.DENIED,
}
DIMENSION_LABELS = {
    "contact": "의심 연락",
    "web": "링크·웹",
    "device": "기기",
    "personal_data": "개인정보",
    "financial_data": "금융정보",
    "authentication": "인증정보",
    "financial_loss": "금전 피해",
}
REDACTION_LABELS = {
    "resident_id": "주민등록번호",
    "phone": "전화번호",
    "email": "이메일 주소",
    "card": "카드번호",
    "auth_code": "인증번호",
    "password": "비밀번호",
    "account": "계좌번호",
}
CLARIFICATION_LABELS = {
    "money_transferred": "송금·현금 전달 여부",
    "remote_control_enabled": "원격제어 허용 여부",
    "app_installed": "앱 설치 여부",
    "auth_secret_shared": "인증정보 전달 여부",
    "financial_info_shared": "금융정보 전달 여부",
    "personal_info_shared": "개인정보 전달 여부",
    "link_clicked": "링크 클릭 여부",
}
ANSWER_LABELS = {
    ActionStatus.DONE: "예",
    ActionStatus.DENIED: "아니오",
    ActionStatus.UNKNOWN: "잘 모르겠음",
}

def load_styles() -> str:
    """Load the app stylesheet from the static asset file."""

    stylesheet = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    return f"<style>{stylesheet}</style>"


def clear_clarification_state() -> None:
    """Clear feedback and radio values left by a previous analysis."""

    st.session_state.pop("confirmation_feedback", None)
    st.session_state.pop("clarification_answered_actions", None)
    st.session_state.pop("clarification_completed", None)
    st.session_state.pop("redacted_types", None)
    st.session_state.pop("clarification_answers", None)
    for key in tuple(st.session_state):
        if key.startswith("answer_"):
            del st.session_state[key]


def privacy_notice_text(redacted_types: tuple[str, ...]) -> str | None:
    """Describe local redaction without ever echoing a sensitive value."""

    labels = tuple(
        REDACTION_LABELS[data_type]
        for data_type in redacted_types
        if data_type in REDACTION_LABELS
    )
    if not labels:
        return None
    detected = ", ".join(dict.fromkeys(labels))
    return (
        f"민감정보가 감지되어 {detected}를 외부 AI 전송 전에 "
        "자동 마스킹했습니다."
    )


def no_immediate_guide_message(*, has_follow_up_guides: bool) -> str:
    """Avoid claiming there is no response when confirmed harm has a later guide."""

    if has_follow_up_guides:
        return "확인된 노출이 있습니다. 아래의 후속 대응 지침을 바로 확인하세요."
    return (
        "입력만으로 확정된 긴급 행동이 없습니다. "
        "추가 확인과 공식 채널 확인이 필요합니다."
    )


def _display_action_state(
    analysis: StructuredAnalysis,
    actions: tuple[str, ...],
    *,
    confirmed_value: str,
    confirmed_tone: str,
) -> tuple[str, str]:
    statuses = {analysis.actions[action].status for action in actions}
    if ActionStatus.DONE in statuses:
        return confirmed_value, confirmed_tone
    if statuses & {ActionStatus.UNKNOWN, ActionStatus.REQUESTED}:
        return "추가 확인 필요", "caution"
    if ActionStatus.DENIED in statuses:
        return "사용자가 아니오로 확인", "info"
    return "언급 없음", "info"


def status_summary(analysis: StructuredAnalysis) -> tuple[tuple[str, str, str], ...]:
    """Preserve confirmed, denied, uncertain, and unmentioned states in the UI."""

    dimensions = (
        ("기기 노출", ("app_installed", "remote_control_enabled"), "위험", "danger"),
        (
            "개인정보 노출",
            ("personal_info_shared", "financial_info_shared"),
            "확인됨",
            "caution",
        ),
        ("인증정보 노출", ("auth_secret_shared",), "확인됨", "caution"),
        ("금전 피해", ("money_transferred",), "발생", "danger"),
    )
    return tuple(
        (
            label,
            *_display_action_state(
                analysis,
                actions,
                confirmed_value=confirmed_value,
                confirmed_tone=confirmed_tone,
            ),
        )
        for label, actions, confirmed_value, confirmed_tone in dimensions
    )


def render_status_grid(analysis: StructuredAnalysis) -> None:
    cards = "".join(
        (
            f'<div class="status-card {tone}">'
            f'<div class="label">{escape(label)}</div>'
            f'<div class="value">{escape(value)}</div></div>'
        )
        for label, value, tone in status_summary(analysis)
    )
    st.markdown(f'<div class="status-grid">{cards}</div>', unsafe_allow_html=True)


def clarification_answer_summary(
    answers: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    """Return stable user-facing labels for answers retained in session state."""

    rows = []
    for action, label in CLARIFICATION_LABELS.items():
        raw_status = answers.get(action)
        if raw_status is None:
            continue
        try:
            status = ActionStatus(raw_status)
        except ValueError:
            continue
        if status in ANSWER_LABELS:
            rows.append((label, ANSWER_LABELS[status]))
    return tuple(rows)


def completed_clarification_actions(
    previously_answered: set[str], answers: dict[str, ActionStatus]
) -> tuple[str, ...]:
    """Mark every submitted question complete, including unknown answers."""

    return tuple(sorted(previously_answered | set(answers)))


def level_zero_explanation(
    analysis: StructuredAnalysis, redacted_types: tuple[str, ...]
) -> str:
    """Explain why no confirmed exposure currently produces LEVEL 0."""

    statuses = {observation.status for observation in analysis.actions.values()}
    sentences = ["현재 입력과 확인 답변에서 금융사기 피해 행동은 확인되지 않았습니다."]
    if ActionStatus.DENIED in statuses:
        sentences.append("일부 행동은 사용자가 발생하지 않았다고 확인했습니다.")
    if statuses & {ActionStatus.UNKNOWN, ActionStatus.REQUESTED}:
        sentences.append("아직 불명확한 행동은 추가 확인이 필요합니다.")
    labels = [
        REDACTION_LABELS[data_type]
        for data_type in redacted_types
        if data_type in REDACTION_LABELS
    ]
    if labels:
        sentences.append(
            f"입력된 {', '.join(dict.fromkeys(labels))}는 자동 마스킹했으며, "
            "입력란에 존재했다는 사실만으로 상대방에게 전달된 것으로 판단하지 않습니다."
        )
    sentences.append("안전하다는 확정은 아니므로 필요한 경우 공식 채널로 확인하세요.")
    return " ".join(sentences)


def render_compound_summary(assessment) -> None:
    """Explain when several exposure dimensions require a combined response."""

    if not assessment.is_compound:
        return
    ordered_dimensions = tuple(
        dimension
        for dimension in DIMENSION_LABELS
        if dimension in assessment.harm_dimensions
    )
    chips = "".join(
        f'<span class="compound-chip">{escape(DIMENSION_LABELS[dimension])}</span>'
        for dimension in ordered_dimensions
    )
    tone = "danger" if assessment.financial_loss else "caution"
    st.markdown(
        f'<div class="compound-summary {tone}">'
        f'<div class="compound-title">복합 노출 감지 · {len(ordered_dimensions)}개 영역</div>'
        f'<div class="compound-chips">{chips}</div>'
        '<div class="compound-copy">한 가지 피해 단계만 처리하지 않고, 확인된 모든 노출의 '
        '대응 행동을 합쳐 긴급도 순으로 안내합니다.</div></div>',
        unsafe_allow_html=True,
    )


def render_guide_card(guide, *, number: int | None = None) -> None:
    heading = f"{number}. {guide.title}" if number is not None else guide.title
    with st.container(border=True):
        if guide.priority == "IMMEDIATE":
            st.error(f"**{heading}**\n\n{guide.instruction}", icon="🚨")
        elif guide.priority == "NEXT":
            st.warning(f"**{heading}**\n\n{guide.instruction}", icon="⚠️")
        else:
            st.info(f"**{heading}**\n\n{guide.instruction}", icon="ℹ️")
        st.markdown(
            f"출처: [{guide.issuing_authority} · {guide.source_title}]"
            f"({guide.source_url}) · 확인일 {guide.verified_at.isoformat()}"
        )


def render_result(
    analysis: StructuredAnalysis,
    *,
    redacted_types: tuple[str, ...] = (),
    clarification_answers: dict[str, str] | None = None,
) -> None:
    assessment = assess_exposure(analysis)
    guides = compose_guides(
        assessment, load_guides(ROOT / "data" / "response_guides.json")
    )
    immediate = [guide for guide in guides if guide.priority == "IMMEDIATE"]
    later = [guide for guide in guides if guide.priority != "IMMEDIATE"]

    st.markdown("---")
    render_compound_summary(assessment)
    st.header("🚨 지금 즉시 할 일")
    st.markdown(
        '<div class="section-note">빨간 카드는 피해 확산을 막기 위해 먼저 실행할 행동입니다.</div>',
        unsafe_allow_html=True,
    )
    if immediate:
        for number, guide in enumerate(immediate, 1):
            render_guide_card(guide, number=number)
    else:
        st.info(no_immediate_guide_message(has_follow_up_guides=bool(later)))

    st.header("현재 노출 상태")
    st.markdown(
        '<div class="section-note">입력과 확인 답변에서 발견된 상태입니다. '
        '“확인 안 됨”은 안전하다는 뜻이 아닙니다.</div>',
        unsafe_allow_html=True,
    )
    render_status_grid(analysis)

    answer_rows = clarification_answer_summary(clarification_answers or {})
    if answer_rows:
        with st.container(border=True):
            st.subheader("추가 확인 답변")
            for label, answer in answer_rows:
                st.write(f"**{label}:** {answer}")

    level = int(assessment.representative_level)
    with st.container(border=True):
        st.subheader(f"대표 피해 단계 · LEVEL {level}")
        st.write(LEVEL_NAMES[level])
    if level == 0:
        st.warning(level_zero_explanation(analysis, redacted_types))

    if analysis.risk_signals:
        with st.expander("감지된 위험 신호와 상세 상태"):
            for signal in analysis.risk_signals:
                st.write(f"• {signal}")
            for exposure in sorted(assessment.confirmed_exposures):
                st.write(f"✓ {exposure}")

    if later:
        st.header("⚠️ 다음 행동과 증거 보존")
        st.markdown(
            '<div class="section-note">노란 카드는 주의해서 이어서 할 일, '
            '파란 카드는 안내와 증거 보존 정보입니다.</div>',
            unsafe_allow_html=True,
        )
        for guide in later:
            render_guide_card(guide)

    if guides:
        with st.expander("전체 공식 근거 모아보기"):
            seen = set()
            for guide in guides:
                key = (guide.source_url, guide.source_title)
                if key not in seen:
                    st.markdown(
                        f"- [{guide.issuing_authority} · {guide.source_title}]"
                        f"({guide.source_url}) — 확인일 {guide.verified_at.isoformat()}"
                    )
                    seen.add(key)


def main() -> None:
    st.set_page_config(
        page_title="AI 금융사기 응급대응 비서",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(load_styles(), unsafe_allow_html=True)
    st.markdown(
        '<div class="brand-bar"><div class="brand-lockup">'
        '<span class="brand-mark">S</span><span>세이프스텝</span></div>'
        '<div class="brand-meta">AI FINANCIAL SCAM RESPONSE</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="emergency-grid">'
        '<div class="emergency-card red"><div class="tag">01 · 송금 피해</div>'
        '<div class="headline">이미 송금했다면<br>금융회사 또는 112에 즉시 알리세요.</div>'
        '<div class="detail">AI 분석을 기다리지 말고 지급정지 가능 여부를 먼저 확인합니다.</div></div>'
        '<div class="emergency-card yellow"><div class="tag">02 · 앱 설치</div>'
        '<div class="headline">해당 기기에서 금융·인증 앱 사용을 중단하세요.</div>'
        '<div class="detail">안전한 다른 기기를 이용하세요.</div></div>'
        '<div class="emergency-card blue"><div class="tag">03 · 입력 주의</div>'
        '<div class="headline">민감한 번호와 비밀번호는 입력하지 마세요.</div>'
        '<div class="detail">입력값은 분석 전 로컬에서 마스킹합니다.</div></div></div>',
        unsafe_allow_html=True,
    )

    samples = load_samples(ROOT / "data" / "sample_cases.json")
    labels = ["직접 입력"] + [sample.label for sample in samples]
    intro_column, input_column = st.columns([1.05, 0.95], gap="large")
    with intro_column, st.container(key="intro_panel"):
        st.markdown(
            '<div class="hero-copy"><div class="eyebrow">● AI 금융 보안 대응</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="hero-title">의심되는 순간,<span>해야 할 일부터 알려드립니다.</span></div>'
            '<div class="hero-lead">복잡한 금융사기 정보를 직접 찾지 않아도 됩니다. '
            '현재 상황을 입력하면 노출 상태와 행동 순서를 공식 근거와 함께 정리합니다.</div>'
            '<div class="process-list">'
            '<div class="process-item"><div class="process-number">01</div><div class="process-text">'
            '<strong>상황 입력</strong><span>기억나는 사실을 자연어로 작성</span></div></div>'
            '<div class="process-item"><div class="process-number">02</div><div class="process-text">'
            '<strong>안전한 상태 판단</strong><span>AI 추출과 규칙 엔진을 분리해 검증</span></div></div>'
            '<div class="process-item"><div class="process-number">03</div><div class="process-text">'
            '<strong>즉시 행동 확인</strong><span>공식 출처 기반 대응을 우선순위로 제공</span></div></div>'
            '</div><div class="trust-row">'
            '<span class="trust-chip">✓ <strong>개인정보 미저장</strong></span>'
            '<span class="trust-chip">✓ <strong>공식 출처 기반</strong></span>'
            '<span class="trust-chip">✓ <strong>AI 판단 범위 제한</strong></span>'
            '</div>',
            unsafe_allow_html=True,
        )

    with input_column, st.container(border=False, key="analysis_panel"):
        st.markdown(
            '<div class="panel-heading"><div class="small">QUICK CHECK · 약 10초</div>'
            '<div class="large">현재 상황을 알려주세요</div>'
            '<div class="copy">긴 문장 대신 기억나는 사실만 간단히 적어도 됩니다.</div></div>',
            unsafe_allow_html=True,
        )
        selected_label = st.selectbox("예시 상황", labels)
        selected = next(
            (sample for sample in samples if sample.label == selected_label), None
        )
        default_text = selected.text if selected else ""
        situation = st.text_area(
            "의심되는 상황을 설명해주세요",
            value=default_text,
            height=150,
            max_chars=3000,
            placeholder="예: 검찰이라고 전화가 와서 앱 설치와 송금을 요구했습니다.",
        )
        analyze_clicked = st.button(
            "상황 분석하기", type="primary", use_container_width=True
        )

    if analyze_clicked:
        clear_clarification_state()
        if selected and situation.strip() == selected.text:
            st.session_state.analysis = selected.analysis
            st.session_state.sample_mode = True
            st.session_state.redacted_types = ()
        else:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if api_key:
                result = analyze_text(situation, OpenAIStructuredExtractor(api_key=api_key))
                if result.used_fallback:
                    result = analyze_text(situation, LocalKoreanRuleExtractor())
                    st.session_state.analysis_mode = "local_fallback"
                else:
                    st.session_state.analysis_mode = "llm"
            else:
                result = analyze_text(situation, LocalKoreanRuleExtractor())
                st.session_state.analysis_mode = "local"
            st.session_state.analysis = result.analysis
            st.session_state.redacted_types = result.redacted_types
            st.session_state.sample_mode = False

    analysis = st.session_state.get("analysis")
    if analysis:
        confirmation_feedback = st.session_state.pop("confirmation_feedback", None)
        if confirmation_feedback:
            st.toast("추가 답변이 정상적으로 반영되었습니다.", icon="✅")
            st.success(confirmation_feedback, icon="✅")
        if st.session_state.get("sample_mode"):
            st.caption("샘플 모드: 사전 정의된 기대 분석 결과로 전체 대응 흐름을 시연합니다.")
        elif st.session_state.get("analysis_mode") == "local":
            st.info(
                "현재는 주요 금융사기 표현을 인식하는 로컬 규칙 분석 결과입니다. "
                "불명확한 항목은 추가 질문과 공식 채널을 통해 확인하세요."
            )
        elif st.session_state.get("analysis_mode") == "local_fallback":
            st.warning(
                "AI 연결이 원활하지 않아 로컬 규칙으로 분석했습니다. "
                "고정 긴급 안내와 공식 확인 경로를 우선 확인하세요."
            )
        privacy_notice = privacy_notice_text(
            tuple(st.session_state.get("redacted_types", ()))
        )
        if privacy_notice:
            st.info(privacy_notice, icon="🛡️")
        answered_actions = set(
            st.session_state.get("clarification_answered_actions", ())
        )
        if st.session_state.get("clarification_completed"):
            questions = ()
        else:
            questions = tuple(
                question
                for question in select_questions(analysis)
                if question.action not in answered_actions
            )
        if questions:
            st.subheader("추가 확인")
            st.caption("답변을 반영하면 아래 위험 상태와 행동 지침을 즉시 다시 계산합니다.")
            with st.form("clarification_form", border=True):
                raw_answers = {
                    question.action: st.radio(
                        question.prompt,
                        ANSWER_MAP.keys(),
                        index=None,
                        horizontal=True,
                        key=f"answer_{question.action}",
                    )
                    for question in questions
                }
                answers_submitted = st.form_submit_button(
                    "답변 반영하고 결과 업데이트",
                    type="primary",
                    use_container_width=True,
                )
            if answers_submitted:
                unanswered_count = sum(answer is None for answer in raw_answers.values())
                if unanswered_count:
                    st.warning(
                        f"답변하지 않은 항목이 {unanswered_count}개 있습니다. "
                        "각 항목을 선택한 뒤 다시 눌러주세요.",
                        icon="⚠️",
                    )
                else:
                    answers = {
                        action: ANSWER_MAP[answer]
                        for action, answer in raw_answers.items()
                        if answer is not None
                    }
                    with st.spinner("답변을 반영해 대응 결과를 다시 계산하고 있습니다..."):
                        updated_analysis = apply_answers(analysis, answers)
                        unknown_count = sum(
                            status is ActionStatus.UNKNOWN
                            for status in answers.values()
                        )
                        st.session_state.analysis = updated_analysis
                        st.session_state.clarification_answered_actions = (
                            completed_clarification_actions(answered_actions, answers)
                        )
                        retained_answers = dict(
                            st.session_state.get("clarification_answers", {})
                        )
                        retained_answers.update(
                            {
                                action: status.value
                                for action, status in answers.items()
                            }
                        )
                        st.session_state.clarification_answers = retained_answers
                        st.session_state.clarification_completed = True
                        if unknown_count:
                            feedback = (
                                "답변을 모두 반영했습니다. ‘잘 모르겠음’으로 답한 "
                                f"{unknown_count}개 항목은 미확인 상태로 유지하고, "
                                "안전 우선 기준으로 행동 지침을 업데이트했습니다."
                            )
                        else:
                            feedback = (
                                "추가 확인을 완료하고 위험 상태와 행동 지침을 업데이트했습니다. "
                                "아래의 ‘지금 즉시 할 일’을 확인하세요."
                            )
                        st.session_state.confirmation_feedback = feedback
                    st.rerun()
        render_result(
            analysis,
            redacted_types=tuple(st.session_state.get("redacted_types", ())),
            clarification_answers=dict(
                st.session_state.get("clarification_answers", {})
            ),
        )

    st.markdown(
        '<div class="footer-note">본 서비스는 금융회사·수사기관을 대체하지 않는 대응 보조 도구입니다.<br>'
        '중요한 사실과 절차는 반드시 공식 기관을 통해 다시 확인하세요.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
