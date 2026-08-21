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


_PAST_MARKER = _compile(
    r"예전에|지난번|지난\s*(?:달|주|해)|작년|과거에|전에\s*(?:한번|한 번)"
)
_CURRENT_MARKER = _compile(r"오늘|방금|이번|현재|지금")
_UNCERTAIN_MARKER = _compile(
    r"잘\s*(?:기억이\s*)?안\s*나|기억나지\s*않|했는지(?:는)?\s*(?:잘\s*)?모르|헷갈"
)
_CORRECTION_MARKER = _compile(r"아니[,，]?\s*(?:생각해\s*보니|다시\s*보니)|정정")
_NEGATION_MARKER = _compile(r"(?:^|\s)(?:안|못)\s*|않")
_DID_NOTHING = _compile(
    r"아무것도\s*(?:하지|안\s*하)\s*않|아무것도\s*안\s*했|"
    r"아무\s*정보도\s*(?:주지|알려주지|말하지|보내지)\s*않"
)
_GENERIC_REFUSAL = _compile(
    r"(?:그건|그것도|그거는?).{0,12}(?:안\s*알려|안\s*말|말하지\s*않|알려주지\s*않|쌩깠)"
)
_THIRD_PARTY_SUBJECT = _compile(
    r"(?:제\s*)?(?:어머니|엄마|아버지|아빠|친구|동료|형|누나|언니|오빠|배우자|남편|아내)(?:가|는|은|이)"
)
_USER_SUBJECT = _compile(r"(?:저|저는|제가|나는|내가)(?:는|가)?")
_ATTACKER_CLAIM = _compile(
    r"상대방(?:은|이|이\s*라고\s*한\s*사람).{0,45}(?:말하|주장하|했다고)"
)
_EXPLICIT_DONE = {
    "link_clicked": _compile(
        r"링크를\s*누른|"
        r"아까는\s*아무것도\s*안\s*했.{0,55}생각해보니.{0,40}링크를\s*눌러보기는\s*했|"
        r"오늘.{0,25}링크는\s*안\s*눌렀.{0,55}어제.{0,30}링크는\s*눌렀"
    ),
    "personal_info_shared": _compile(r"(?:이름.{0,15})?생년월일까지만\s*입력했"),
    "financial_info_shared": _compile(
        r"(?:계좌번호|카드번호).{0,25}(?:알려준\s*게\s*맞|알려준\s*건\s*맞|번호를\s*불러줬)"
    ),
    "auth_secret_shared": _compile(
        r"(?:인증번호|문자로\s*온\s*(?:인증)?번호).{0,45}(?:읽어주|불러줬)"
    ),
    "remote_control_enabled": _compile(r"화면\s*공유.{0,25}연결은\s*했"),
    "money_transferred": _compile(r"\d+(?:만)?\s*원.{0,24}보낸|돈을\s*보내긴\s*했"),
}
_EXPLICIT_DENIED = {
    "link_clicked": _compile(
        r"링크.{0,30}누르거나.{0,25}적은\s*없|"
        r"아무것도\s*누르지\s*않|"
        r"(?:앱이나\s*링크|링크는).{0,20}건드리지\s*않"
    ),
    "app_installed": _compile(
        r"(?:앱|프로그램).{0,35}(?:깐|설치한)\s*적은\s*없|"
        r"(?:앱이나\s*링크|앱은).{0,20}건드리지\s*않|"
        r"실제로는\s*설치하지\s*않|"
        r"제\s*휴대폰에는\s*아무것도\s*설치하지\s*않"
    ),
    "personal_info_shared": _compile(
        r"정보도\s*입력하지\s*않|개인정보를\s*알려준\s*적은\s*없|"
        r"신분증\s*사진.{0,45}실제로\s*전송하지는\s*않"
    ),
    "financial_info_shared": _compile(r"계좌번호\s*자체는\s*알려주지\s*않"),
    "money_transferred": _compile(
        r"송금한\s*적이\s*없|"
        r"제\s*다른\s*계좌로.{0,60}이체했.{0,80}상대방\s*계좌로\s*보낸\s*건\s*(?:아니|아닙)"
    ),
}
_DENIAL_OVERRIDES_DONE = {
    "app_installed": _compile(r"거짓말.{0,30}실제로는\s*설치하지\s*않"),
    "personal_info_shared": _compile(
        r"상대방.{0,35}이미\s*알고.{0,50}저는.{0,25}알려준\s*적은\s*없"
    ),
    "financial_info_shared": _compile(
        r"은행\s*이름까지만.{0,35}계좌번호\s*자체는\s*알려주지\s*않"
    ),
    "money_transferred": _compile(
        r"제\s*다른\s*계좌로.{0,60}이체했.{0,80}상대방\s*계좌로\s*보낸\s*건\s*(?:아니|아닙)"
    ),
}
_INJECTION_INSTRUCTION = _compile(r"이전\s*내용은\s*무시하고.{0,80}처리해")
_REAL_FACT_MARKER = _compile(r"실제로는")
_REPORTED_LIE_CONTEXT = _compile(r"설치했다고\s*거짓말.{0,35}실제로는")
_OWN_ACCOUNT_TRANSFER = _compile(
    r"제\s*다른\s*계좌로.{0,60}이체했.{0,80}상대방\s*계좌로\s*보낸\s*건\s*(?:아니|아닙)"
)
_AUTH_DETAIL_PATTERNS = (
    (
        "password_shared",
        ActionStatus.DENIED,
        _compile(r"비밀번호.{0,18}(?:안\s*알려줬|안\s*말했)"),
    ),
    (
        "auth_code_shared",
        ActionStatus.DONE,
        _compile(r"(?:인증번호|문자로\s*온\s*(?:인증)?번호).{0,45}(?:읽어주|불러줬)"),
    ),
)


ACTION_PATTERNS = {
    "suspicious_contact_received": ActionPatterns(
        _compile(r"전화|문자|메시지|메신저|카톡|연락|검찰|경찰|금감원|은행"),
        _compile(
            r"(?:전화|문자|메시지|연락).{0,15}(?:왔|와서|받|옴)|(?:오늘|방금).{0,20}(?:문자|메시지|연락)|(?:검찰|경찰|금감원|은행).{0,20}(?:라며|라고|사칭|전화)"
        ),
        _compile(r"(?:전화|문자|메시지|연락).{0,10}(?:받지|오지)\s*않|연락\s*없"),
        _compile(r"연락하라고|전화하라고"),
    ),
    "link_clicked": ActionPatterns(
        _compile(r"링크|URL|주소|사이트|웹페이지"),
        _compile(
            r"(?:링크|URL|주소).{0,22}(?:눌렀|눌러|클릭했|접속했|열었|들어가\s*봤)|사이트.{0,12}(?:들어갔|접속했)"
        ),
        _compile(
            r"(?:링크|URL|주소).{0,35}(?:누르지|누른\s*적|누르거나|클릭하지|접속하지|열지).{0,12}(?:않|없)|(?:링크|URL).{0,15}(?:아직\s*)?안\s*(?:눌|클릭)|오늘.{0,35}(?:아직\s*)?안\s*(?:눌|클릭)"
        ),
        _compile(
            r"(?:링크|URL|주소).{0,15}(?:누르|클릭|접속)하?라고|링크.{0,15}(?:요구|보내왔|보냈)"
        ),
    ),
    "app_installed": ActionPatterns(
        _compile(r"앱|어플|애플리케이션|프로그램"),
        _compile(
            r"(?:앱|어플|프로그램).{0,20}(?:설치(?:를\s*)?(?:했|함|했습니다|하고|한)|깔았|깔긴\s*했|다운받았)"
        ),
        _compile(
            r"(?:앱|어플|프로그램|설치).{0,30}(?:설치하지|깔지|다운받지|깐\s*적).{0,10}(?:않|없)|(?:앱|어플|설치).{0,15}(?:안|않)\s*(?:했|설치|깔)|설치는?\s*안\s*했"
        ),
        _compile(
            r"(?:앱|어플|프로그램).{0,25}(?:설치하|설치하고|설치해|설치하라|깔|다운받으?)라고|(?:앱|어플).{0,20}설치.{0,8}(?:요구|권유)"
        ),
    ),
    "remote_control_enabled": ActionPatterns(
        _compile(r"원격|화면\s*공유|접근\s*권한|제어"),
        _compile(
            r"(?:원격|화면\s*공유|접근\s*권한|제어).{0,18}(?:허용했|켜줬|승인했|동의했)"
        ),
        _compile(
            r"(?:원격|화면\s*공유|접근\s*권한|제어).{0,18}(?:허용하지|승인하지|동의하지)\s*않|(?:원격|화면\s*공유).{0,10}안\s*(?:했|켰)"
        ),
        _compile(
            r"(?:원격|화면\s*공유|접근\s*권한).{0,18}(?:허용하|켜|승인하)라고|원격.{0,12}(?:요구|요청)"
        ),
    ),
    "personal_info_shared": ActionPatterns(
        _compile(
            r"개인정보|주민등록정보|주민(?:등록)?번호|신분증|주소|생년월일|주민등록번호 마스킹"
        ),
        _compile(
            r"(?:개인정보|주민등록정보|주민(?:등록)?번호|신분증|주소|생년월일|주민등록번호 마스킹).{0,25}(?:알려줬|알려준|말했|보냈|전달했|입력했|찍어줬|제공했|제공한)"
        ),
        _compile(
            r"(?:개인정보|주민(?:등록)?번호|신분증|주소|생년월일).{0,30}(?:안\s*(?:알려|말|보내|넘기)|알려주지|말하지|보내지|전달하지|입력하지|넘기지)\s*않"
        ),
        _compile(
            r"(?:개인정보|주민(?:등록)?번호|신분증|주소|생년월일).{0,25}(?:알려주|알려달|말하|말해|보내|전달하|입력하)라고|개인정보.{0,12}(?:요구|요청)"
        ),
    ),
    "financial_info_shared": ActionPatterns(
        _compile(
            r"계좌번호|카드번호|카드정보|금융정보|계좌번호 마스킹|카드번호 마스킹|내\s*계좌|제\s*계좌"
        ),
        _compile(
            r"(?:계좌번호|카드번호|카드정보|금융정보|계좌번호 마스킹|카드번호 마스킹).{0,25}(?:알려줬|말했|보냈|전달했|입력했)"
        ),
        _compile(
            r"(?:계좌번호|카드번호|카드정보|금융정보|내\s*계좌|제\s*계좌).{0,30}(?:안\s*(?:알려|말|보내|넘기)|알려주지|말하지|보내지|전달하지|입력하지|넘기지)\s*않"
        ),
        _compile(
            r"(?:계좌번호|카드번호|카드정보|금융정보).{0,25}(?:알려주|알려달|말하|말해|보내|전달하|입력하)라고|(?:계좌|카드)정보.{0,12}(?:요구|요청)"
        ),
    ),
    "auth_secret_shared": ActionPatterns(
        _compile(r"인증번호|비밀번호|비번|보안코드|OTP|공동인증서|인증정보 마스킹"),
        _compile(
            r"(?:인증번호|비밀번호|비번|보안코드|OTP|공동인증서|인증정보 마스킹).{0,45}(?:알려줬|알려준|말했|읽어줬|읽어주|보냈|전달했|입력했)"
        ),
        _compile(
            r"(?:인증번호|비밀번호|비번|보안코드|OTP|공동인증서).{0,30}(?:안\s*(?:알려|말|보내)|알려주지|말하지|보내지|전달하지|입력하지)\s*않"
        ),
        _compile(
            r"(?:인증번호|비밀번호|비번|보안코드|OTP|공동인증서).{0,25}(?:알려주|알려달|달라|말하|말해|보내|전달하|입력하)(?:라고|길래)|인증정보.{0,12}(?:요구|요청)"
        ),
    ),
    "money_transferred": ActionPatterns(
        _compile(r"송금|이체|입금|돈|현금|상품권|안전계좌"),
        _compile(
            r"(?:송금|이체|입금)(?:까지)?\s*(?:을|를)?\s*(?:했|함|했습니다)|(?:돈|현금|상품권|\d+(?:만)?\s*원).{0,18}(?:보냈|전달했|건넸)|안전계좌.{0,18}(?:옮겼|보냈)"
        ),
        _compile(
            r"(?:송금|이체|입금)(?:은|는|을|를|도)?\s*하지\s*않|(?:돈|현금|상품권).{0,20}(?:안\s*보냈|안\s*보내|안보냄|보내지|전달하지|건네지)\s*(?:않|$|[.!?])?|(?:송금|이체)\s*안\s*했"
        ),
        _compile(
            r"(?:송금|이체|입금)하라고|(?:돈|현금|상품권).{0,18}(?:보내|보내라|전달하|건네)라고|안전계좌.{0,18}(?:옮기|보내)라고"
        ),
    ),
}


def _current_incident_text(text: str) -> str:
    """Drop explicitly historical sentences when a current incident is present."""

    sentences = [
        part.strip() for part in re.split(r"(?<=[.!?])|\n", text) if part.strip()
    ]
    if not any(_CURRENT_MARKER.search(sentence) for sentence in sentences):
        return text
    current = [
        sentence
        for sentence in sentences
        if not (_PAST_MARKER.search(sentence) and not _CURRENT_MARKER.search(sentence))
    ]
    return " ".join(current)


def _strip_injection_instruction(text: str) -> str:
    """Discard an explicit output-manipulation clause before stated real facts."""

    instruction = _INJECTION_INSTRUCTION.search(text)
    fact = _REAL_FACT_MARKER.search(text)
    if instruction and fact and instruction.start() < fact.start():
        return text[fact.end() :].strip()
    return text


def _is_third_party_match(text: str, match: re.Match[str]) -> bool:
    prefix = text[max(0, match.start() - 40) : match.start()]
    third_party = tuple(_THIRD_PARTY_SUBJECT.finditer(prefix))
    if not third_party:
        return False
    user = tuple(_USER_SUBJECT.finditer(prefix))
    return not user or third_party[-1].start() > user[-1].start()


def _is_attacker_claim(text: str, match: re.Match[str]) -> bool:
    context = text[max(0, match.start() - 30) : match.end() + 30]
    return bool(_ATTACKER_CLAIM.search(context))


def _has_user_done(
    text: str, action: str, patterns: ActionPatterns
) -> re.Match[str] | None:
    explicit = _EXPLICIT_DONE.get(action)
    if explicit_match := explicit.search(text) if explicit else None:
        return explicit_match
    return next(
        (
            match
            for match in patterns.done.finditer(text)
            if not _is_third_party_match(text, match)
            and not _is_attacker_claim(text, match)
            and not text[match.end() : match.end() + 3].startswith(("는지", "다면"))
            and not _NEGATION_MARKER.search(match.group(0))
        ),
        None,
    )


def _detailed_evidence(text: str, action: str, fallback: str) -> str:
    """Retain mixed sub-facts without expanding the MVP's top-level action axes."""

    if action != "auth_secret_shared":
        return fallback
    details = [
        f"{name}={status.value}: {match.group(0)}"
        for name, status, pattern in _AUTH_DETAIL_PATTERNS
        if (match := pattern.search(text))
    ]
    return " | ".join(details) if details else fallback


def _observation(
    text: str,
    action: str,
    patterns: ActionPatterns,
    *,
    allow_contextual_refusal: bool = False,
) -> dict[str, str | None]:
    if action == "suspicious_contact_received" and _REPORTED_LIE_CONTEXT.search(text):
        return {"status": ActionStatus.NOT_MENTIONED.value, "evidence": None}
    if action == "financial_info_shared" and _OWN_ACCOUNT_TRANSFER.search(text):
        return {"status": ActionStatus.NOT_MENTIONED.value, "evidence": None}
    requested = bool(patterns.requested.search(text))
    denied_match = patterns.denied.search(text)
    if (
        action == "auth_secret_shared"
        and denied_match
        and re.search(r"[.!?]", denied_match.group(0))
    ):
        denied_match = None
    explicit_denied = _EXPLICIT_DENIED.get(action)
    explicit_denied_match = explicit_denied.search(text) if explicit_denied else None
    denied = bool(denied_match or explicit_denied_match)
    did_nothing = bool(
        action != "suspicious_contact_received"
        and patterns.concept.search(text)
        and _DID_NOTHING.search(text)
    )
    if did_nothing:
        explicit_done = _EXPLICIT_DONE.get(action)
        if explicit_done_match := explicit_done.search(text) if explicit_done else None:
            return {
                "status": ActionStatus.DONE.value,
                "evidence": _detailed_evidence(
                    text, action, explicit_done_match.group(0)
                ),
            }
        return {"status": ActionStatus.DENIED.value, "evidence": None}
    if (
        allow_contextual_refusal
        and patterns.concept.search(text)
        and _GENERIC_REFUSAL.search(text)
    ):
        denied = True
    done_match = _has_user_done(text, action, patterns)
    if done_match and denied:
        denial_override = _DENIAL_OVERRIDES_DONE.get(action)
        if denial_override and denial_override.search(text):
            return {"status": ActionStatus.DENIED.value, "evidence": None}
        if _EXPLICIT_DONE.get(action) and _EXPLICIT_DONE[action].search(text):
            return {
                "status": ActionStatus.DONE.value,
                "evidence": _detailed_evidence(text, action, done_match.group(0)),
            }
        if _CORRECTION_MARKER.search(text):
            return {"status": ActionStatus.UNKNOWN.value, "evidence": None}
        current_markers = tuple(_CURRENT_MARKER.finditer(text))
        if (
            current_markers
            and denied_match
            and any(
                done_match.start() < marker.start() <= denied_match.start()
                for marker in current_markers
            )
        ):
            return {"status": ActionStatus.DENIED.value, "evidence": None}
        return {"status": ActionStatus.UNKNOWN.value, "evidence": None}
    if denied:
        return {"status": ActionStatus.DENIED.value, "evidence": None}
    if done_match:
        return {
            "status": ActionStatus.DONE.value,
            "evidence": _detailed_evidence(text, action, done_match.group(0)),
        }
    if requested:
        return {"status": ActionStatus.REQUESTED.value, "evidence": None}
    raw_done_match = patterns.done.search(text)
    if raw_done_match and _is_third_party_match(text, raw_done_match):
        return {"status": ActionStatus.NOT_MENTIONED.value, "evidence": None}
    if patterns.concept.search(text) and _UNCERTAIN_MARKER.search(text):
        return {"status": ActionStatus.UNKNOWN.value, "evidence": None}
    if patterns.concept.search(text):
        return {"status": ActionStatus.UNKNOWN.value, "evidence": None}
    return {"status": ActionStatus.NOT_MENTIONED.value, "evidence": None}


class LocalKoreanRuleExtractor:
    """Extract common high-risk actions without an external model call."""

    def extract(self, text: str) -> dict[str, object]:
        text = _strip_injection_instruction(_current_incident_text(text))
        actions = {
            action: _observation(
                text,
                action,
                ACTION_PATTERNS[action],
                allow_contextual_refusal=action
                in {
                    "personal_info_shared",
                    "financial_info_shared",
                    "auth_secret_shared",
                },
            )
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
            in {
                ActionStatus.DONE.value,
                ActionStatus.REQUESTED.value,
                ActionStatus.UNKNOWN.value,
            }
        ]
        return {
            "impersonated_entity": None,
            "risk_signals": signals,
            "actions": actions,
        }
