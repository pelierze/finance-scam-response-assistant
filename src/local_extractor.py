"""Bounded Korean rule extractor for core scam-response actions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.models import TRACKED_ACTIONS, ActionStatus


@dataclass(frozen=True)
class ActionPatterns:
    concept: re.Pattern[str]
    done: re.Pattern[str]
    denied: re.Pattern[str]
    requested: re.Pattern[str]


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


ACTION_PATTERNS = {
    "suspicious_contact_received": ActionPatterns(
        _compile(r"전화|문자|메시지|메신저|카톡|연락|검찰|경찰|금감원|은행"),
        _compile(r"(?:전화|문자|메시지|연락).{0,15}(?:왔|와서|받|옴)|(?:검찰|경찰|금감원|은행).{0,12}(?:라며|라고|사칭)"),
        _compile(r"(?:전화|문자|메시지|연락).{0,10}(?:받지|오지)\s*않|연락\s*없"),
        _compile(r"연락하라고|전화하라고"),
    ),
    "link_clicked": ActionPatterns(
        _compile(r"링크|URL|주소|사이트|웹페이지"),
        _compile(r"(?:링크|URL|주소).{0,15}(?:눌렀|클릭했|접속했|열었)|사이트.{0,12}(?:들어갔|접속했)"),
        _compile(r"(?:링크|URL|주소).{0,15}(?:누르지|클릭하지|접속하지|열지)\s*않|(?:링크|URL).{0,10}안\s*(?:눌|클릭)"),
        _compile(r"(?:링크|URL|주소).{0,15}(?:누르|클릭|접속)하?라고|링크.{0,15}(?:요구|보내왔|보냈)"),
    ),
    "app_installed": ActionPatterns(
        _compile(r"앱|어플|애플리케이션|프로그램"),
        _compile(r"(?:앱|어플|프로그램).{0,20}(?:설치(?:를\s*)?(?:했|함|했습니다|하고|한)|깔았|다운받았)"),
        _compile(r"(?:앱|어플|프로그램).{0,20}(?:설치하지|깔지|다운받지)\s*않|(?:앱|어플).{0,12}안\s*(?:설치|깔)"),
        _compile(r"(?:앱|어플|프로그램).{0,20}(?:설치하|깔|다운받으?)라고|(?:앱|어플).{0,20}설치.{0,8}(?:요구|권유)"),
    ),
    "remote_control_enabled": ActionPatterns(
        _compile(r"원격|화면\s*공유|접근\s*권한|제어"),
        _compile(r"(?:원격|화면\s*공유|접근\s*권한|제어).{0,18}(?:허용했|켜줬|승인했|동의했)"),
        _compile(r"(?:원격|화면\s*공유|접근\s*권한|제어).{0,18}(?:허용하지|승인하지|동의하지)\s*않|(?:원격|화면\s*공유).{0,10}안\s*(?:했|켰)"),
        _compile(r"(?:원격|화면\s*공유|접근\s*권한).{0,18}(?:허용하|켜|승인하)라고|원격.{0,12}(?:요구|요청)"),
    ),
    "personal_info_shared": ActionPatterns(
        _compile(r"개인정보|주민등록정보|주민(?:등록)?번호|신분증|주소|생년월일|주민등록번호 마스킹"),
        _compile(r"(?:개인정보|주민등록정보|주민(?:등록)?번호|신분증|주소|생년월일|주민등록번호 마스킹).{0,25}(?:알려줬|알려준|말했|보냈|전달했|입력했|찍어줬|제공했|제공한)"),
        _compile(r"(?:개인정보|주민(?:등록)?번호|신분증|주소|생년월일).{0,20}(?:알려주지|말하지|보내지|전달하지|입력하지)\s*않"),
        _compile(r"(?:개인정보|주민(?:등록)?번호|신분증|주소|생년월일).{0,20}(?:알려주|말하|보내|전달하|입력하)라고|개인정보.{0,12}(?:요구|요청)"),
    ),
    "financial_info_shared": ActionPatterns(
        _compile(r"계좌번호|카드번호|카드정보|금융정보|계좌번호 마스킹|카드번호 마스킹"),
        _compile(r"(?:계좌번호|카드번호|카드정보|금융정보|계좌번호 마스킹|카드번호 마스킹).{0,25}(?:알려줬|말했|보냈|전달했|입력했)"),
        _compile(r"(?:계좌번호|카드번호|카드정보|금융정보).{0,20}(?:알려주지|말하지|보내지|전달하지|입력하지)\s*않"),
        _compile(r"(?:계좌번호|카드번호|카드정보|금융정보).{0,20}(?:알려주|말하|보내|전달하|입력하)라고|(?:계좌|카드)정보.{0,12}(?:요구|요청)"),
    ),
    "auth_secret_shared": ActionPatterns(
        _compile(r"인증번호|비밀번호|보안코드|OTP|공동인증서|인증정보 마스킹"),
        _compile(r"(?:인증번호|비밀번호|보안코드|OTP|공동인증서|인증정보 마스킹).{0,25}(?:알려줬|말했|보냈|전달했|입력했)"),
        _compile(r"(?:인증번호|비밀번호|보안코드|OTP|공동인증서).{0,20}(?:알려주지|말하지|보내지|전달하지|입력하지)\s*않"),
        _compile(r"(?:인증번호|비밀번호|보안코드|OTP|공동인증서).{0,20}(?:알려주|말하|보내|전달하|입력하)라고|인증정보.{0,12}(?:요구|요청)"),
    ),
    "money_transferred": ActionPatterns(
        _compile(r"송금|이체|입금|돈|현금|상품권|안전계좌"),
        _compile(r"(?:송금|이체|입금)(?:까지)?\s*(?:을|를)?\s*(?:했|함|했습니다)|(?:돈|현금|상품권).{0,18}(?:보냈|전달했|건넸)|안전계좌.{0,18}(?:옮겼|보냈)"),
        _compile(r"(?:송금|이체|입금)하지\s*않|(?:돈|현금|상품권).{0,18}(?:보내지|전달하지|건네지)\s*않|(?:송금|이체)\s*안\s*했"),
        _compile(r"(?:송금|이체|입금)하라고|(?:돈|현금|상품권).{0,18}(?:보내|전달하|건네)라고|안전계좌.{0,18}(?:옮기|보내)라고"),
    ),
}


def _observation(text: str, patterns: ActionPatterns) -> dict[str, str | None]:
    if patterns.denied.search(text):
        return {"status": ActionStatus.DENIED.value, "evidence": None}
    match = patterns.done.search(text)
    if match:
        return {"status": ActionStatus.DONE.value, "evidence": match.group(0)}
    if patterns.requested.search(text):
        return {"status": ActionStatus.REQUESTED.value, "evidence": None}
    if patterns.concept.search(text):
        return {"status": ActionStatus.UNKNOWN.value, "evidence": None}
    return {"status": ActionStatus.NOT_MENTIONED.value, "evidence": None}


class LocalKoreanRuleExtractor:
    """Extract common high-risk actions without an external model call."""

    def extract(self, text: str) -> dict[str, object]:
        actions = {
            action: _observation(text, ACTION_PATTERNS[action])
            for action in TRACKED_ACTIONS
        }
        signals = [
            label
            for action, label in (
                ("app_installed", "의심 앱 설치 관련 정황"),
                ("personal_info_shared", "개인정보 노출 관련 정황"),
                ("financial_info_shared", "금융정보 노출 관련 정황"),
                ("auth_secret_shared", "인증정보 노출 관련 정황"),
                ("money_transferred", "금전 전달 관련 정황"),
            )
            if actions[action]["status"]
            in {ActionStatus.DONE.value, ActionStatus.REQUESTED.value, ActionStatus.UNKNOWN.value}
        ]
        return {
            "impersonated_entity": None,
            "risk_signals": signals,
            "actions": actions,
        }
