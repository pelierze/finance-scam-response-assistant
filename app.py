"""Streamlit MVP for immediate finance-scam response guidance."""

from __future__ import annotations

import os
from html import escape
from pathlib import Path

import streamlit as st

from src.analyzer import OpenAIStructuredExtractor, analyze_text
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

def load_styles() -> str:
    """Load the app stylesheet from the static asset file."""

    stylesheet = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    return f"<style>{stylesheet}</style>"


def status_summary(assessment) -> tuple[tuple[str, str, str], ...]:
    """Return label, value, and semantic color tone for the status grid."""

    states = (
        ("기기 노출", bool(assessment.device), "위험", "danger"),
        (
            "개인정보 노출",
            bool(assessment.personal_data or assessment.financial_data),
            "확인됨",
            "caution",
        ),
        ("인증정보 노출", bool(assessment.authentication), "확인됨", "caution"),
        ("금전 피해", bool(assessment.financial_loss), "발생", "danger"),
    )
    return tuple(
        (label, active_value if active else "확인 안 됨", tone if active else "info")
        for label, active, active_value, tone in states
    )


def render_status_grid(assessment) -> None:
    cards = "".join(
        (
            f'<div class="status-card {tone}">'
            f'<div class="label">{escape(label)}</div>'
            f'<div class="value">{escape(value)}</div></div>'
        )
        for label, value, tone in status_summary(assessment)
    )
    st.markdown(f'<div class="status-grid">{cards}</div>', unsafe_allow_html=True)


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


def render_result(analysis: StructuredAnalysis) -> None:
    assessment = assess_exposure(analysis)
    guides = compose_guides(
        assessment, load_guides(ROOT / "data" / "response_guides.json")
    )
    immediate = [guide for guide in guides if guide.priority == "IMMEDIATE"]
    later = [guide for guide in guides if guide.priority != "IMMEDIATE"]

    st.markdown("---")
    st.header("🚨 지금 즉시 할 일")
    st.markdown(
        '<div class="section-note">빨간 카드는 피해 확산을 막기 위해 먼저 실행할 행동입니다.</div>',
        unsafe_allow_html=True,
    )
    if immediate:
        for number, guide in enumerate(immediate, 1):
            render_guide_card(guide, number=number)
    else:
        st.info(
            "입력만으로 확정된 긴급 행동이 없습니다. 추가 확인과 공식 채널 확인이 필요합니다."
        )

    st.header("현재 노출 상태")
    st.markdown(
        '<div class="section-note">입력과 확인 답변에서 발견된 상태입니다. '
        '“확인 안 됨”은 안전하다는 뜻이 아닙니다.</div>',
        unsafe_allow_html=True,
    )
    render_status_grid(assessment)

    level = int(assessment.representative_level)
    with st.container(border=True):
        st.subheader(f"대표 피해 단계 · LEVEL {level}")
        st.write(LEVEL_NAMES[level])
    if level == 0:
        st.warning(
            "현재 입력만으로 위험 상태를 판단하기 어렵습니다. 안전하다는 의미가 아니며 "
            "상대방이 제공한 연락처가 아닌 공식 채널로 확인하세요."
        )

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
        if selected and situation.strip() == selected.text:
            st.session_state.analysis = selected.analysis
            st.session_state.sample_mode = True
        else:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                st.session_state.analysis = None
                st.error(
                    "현재 자유 입력 자동 분석을 사용할 수 없습니다. 샘플 상황을 선택하거나 "
                    "공식 긴급 안내를 먼저 확인하세요."
                )
            else:
                result = analyze_text(situation, OpenAIStructuredExtractor(api_key=api_key))
                st.session_state.analysis = result.analysis
                st.session_state.sample_mode = False
                if result.used_fallback:
                    st.warning("자동 분석을 완료하지 못했습니다. 고정 긴급 안내를 우선 확인하세요.")

    analysis = st.session_state.get("analysis")
    if analysis:
        if st.session_state.get("sample_mode"):
            st.caption("샘플 모드: 사전 정의된 기대 분석 결과로 전체 대응 흐름을 시연합니다.")
        questions = select_questions(analysis)
        if questions:
            st.subheader("추가 확인")
            answers = {
                question.action: ANSWER_MAP[
                    st.radio(
                        question.prompt,
                        ANSWER_MAP.keys(),
                        horizontal=True,
                        key=f"answer_{question.action}",
                    )
                ]
                for question in questions
            }
            if st.button("답변 반영하기"):
                analysis = apply_answers(analysis, answers)
                st.session_state.analysis = analysis
        render_result(analysis)

    st.markdown(
        '<div class="footer-note">본 서비스는 금융회사·수사기관을 대체하지 않는 대응 보조 도구입니다.<br>'
        '중요한 사실과 절차는 반드시 공식 기관을 통해 다시 확인하세요.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
