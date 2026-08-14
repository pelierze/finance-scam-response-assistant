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

CARD_CSS = """
<style>
.status-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; margin:.5rem 0 1rem; }
.status-card { border:1px solid #e2e8f0; border-radius:12px; padding:1rem; background:#fff; }
.status-card .label { color:#475569; font-size:.88rem; margin-bottom:.35rem; }
.status-card .value { font-size:1.05rem; font-weight:700; }
.status-card.danger { border-left:6px solid #dc2626; background:#fff7f7; }
.status-card.danger .value { color:#b91c1c; }
.status-card.caution { border-left:6px solid #d97706; background:#fffbeb; }
.status-card.caution .value { color:#a16207; }
.status-card.info { border-left:6px solid #2563eb; background:#eff6ff; }
.status-card.info .value { color:#1d4ed8; }
.section-note { color:#64748b; font-size:.9rem; margin-top:-.6rem; margin-bottom:.8rem; }
@media (max-width: 640px) { .status-grid { grid-template-columns:1fr; } }
</style>
"""


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
    st.set_page_config(page_title="AI 금융사기 응급대응 비서", page_icon="🛡️")
    st.title("🛡️ AI 금융사기 응급대응 비서")
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    st.caption("금융사기 여부를 확정하지 않고, 현재 상황에서 필요한 대응 행동을 안내합니다.")

    st.error(
        "이미 돈을 송금했다면 분석을 기다리지 말고 금융회사 또는 112에 즉시 피해 사실을 알리세요."
    )
    st.warning(
        "상대방이 설치하도록 한 앱이 있다면 해당 기기에서 금융·인증 앱 사용을 중단하세요."
    )
    st.info("주민등록번호, 계좌번호, 카드번호, 비밀번호, 인증번호를 입력하지 마세요.")

    samples = load_samples(ROOT / "data" / "sample_cases.json")
    labels = ["직접 입력"] + [sample.label for sample in samples]
    selected_label = st.selectbox("예시 상황", labels)
    selected = next((sample for sample in samples if sample.label == selected_label), None)
    default_text = selected.text if selected else ""
    situation = st.text_area(
        "의심되는 상황을 설명해주세요",
        value=default_text,
        height=150,
        max_chars=3000,
    )

    if st.button("상황 분석하기", type="primary", use_container_width=True):
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

    st.divider()
    st.caption(
        "본 서비스는 금융회사·수사기관을 대체하지 않는 대응 보조 도구입니다. "
        "공식 기관을 통해 사실과 절차를 다시 확인하세요."
    )


if __name__ == "__main__":
    main()
