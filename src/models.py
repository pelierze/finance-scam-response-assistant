"""Domain models shared by analyzers and deterministic decision logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class ActionStatus(str, Enum):
    """How confidently an action is known to have happened."""

    DONE = "done"
    REQUESTED = "requested"
    DENIED = "denied"
    UNKNOWN = "unknown"
    NOT_MENTIONED = "not_mentioned"


class RepresentativeLevel(IntEnum):
    """User-facing summary level; never a replacement for exposure details."""

    INSUFFICIENT_INFORMATION = 0
    SUSPICIOUS_CONTACT = 1
    WEB_EXPOSURE = 2
    DEVICE_EXPOSURE = 3
    INFORMATION_EXPOSURE = 4
    FINANCIAL_LOSS = 5


TRACKED_ACTIONS = (
    "suspicious_contact_received",
    "link_clicked",
    "app_installed",
    "remote_control_enabled",
    "personal_info_shared",
    "financial_info_shared",
    "auth_secret_shared",
    "money_transferred",
)


@dataclass(frozen=True)
class ActionObservation:
    """A structured action candidate and the phrase supporting it."""

    status: ActionStatus
    evidence: str | None = None

    def __post_init__(self) -> None:
        if self.status is ActionStatus.DONE and not self.evidence:
            raise ValueError("A completed action must include evidence")
        if self.evidence is not None and not self.evidence.strip():
            raise ValueError("Evidence must be null or non-empty")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ActionObservation:
        if not isinstance(value, dict):
            raise TypeError("Action observation must be an object")
        extra_fields = set(value) - {"status", "evidence"}
        if extra_fields:
            raise ValueError(f"Unexpected action fields: {sorted(extra_fields)}")
        if "status" not in value:
            raise ValueError("Action observation requires status")
        try:
            status = ActionStatus(value["status"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid action status: {value['status']!r}") from exc
        evidence = value.get("evidence")
        if evidence is not None and not isinstance(evidence, str):
            raise TypeError("Evidence must be a string or null")
        return cls(status=status, evidence=evidence)


@dataclass(frozen=True)
class StructuredAnalysis:
    """Validated, model-independent representation of an LLM extraction."""

    impersonated_entity: str | None
    risk_signals: tuple[str, ...]
    actions: dict[str, ActionObservation] = field(repr=False)

    def __post_init__(self) -> None:
        missing = set(TRACKED_ACTIONS) - set(self.actions)
        extra = set(self.actions) - set(TRACKED_ACTIONS)
        if missing or extra:
            raise ValueError(
                f"Action keys must match schema; missing={sorted(missing)}, "
                f"extra={sorted(extra)}"
            )
        if any(not signal.strip() for signal in self.risk_signals):
            raise ValueError("Risk signals must be non-empty strings")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> StructuredAnalysis:
        if not isinstance(value, dict):
            raise TypeError("Structured analysis must be an object")
        expected_fields = {"impersonated_entity", "risk_signals", "actions"}
        extra_fields = set(value) - expected_fields
        missing_fields = expected_fields - set(value)
        if extra_fields or missing_fields:
            raise ValueError(
                f"Analysis fields do not match schema; "
                f"missing={sorted(missing_fields)}, extra={sorted(extra_fields)}"
            )

        entity = value["impersonated_entity"]
        if entity is not None and (not isinstance(entity, str) or not entity.strip()):
            raise TypeError("Impersonated entity must be a non-empty string or null")

        signals = value["risk_signals"]
        if not isinstance(signals, list) or not all(
            isinstance(signal, str) for signal in signals
        ):
            raise TypeError("Risk signals must be a list of strings")

        actions = value["actions"]
        if not isinstance(actions, dict):
            raise TypeError("Actions must be an object")

        return cls(
            impersonated_entity=entity,
            risk_signals=tuple(dict.fromkeys(signals)),
            actions={
                name: ActionObservation.from_dict(observation)
                for name, observation in actions.items()
            },
        )


@dataclass(frozen=True)
class ExposureAssessment:
    """Deterministic assessment retaining every confirmed exposure dimension."""

    contact: frozenset[str] = frozenset()
    web: frozenset[str] = frozenset()
    device: frozenset[str] = frozenset()
    personal_data: frozenset[str] = frozenset()
    financial_data: frozenset[str] = frozenset()
    authentication: frozenset[str] = frozenset()
    financial_loss: frozenset[str] = frozenset()
    representative_level: RepresentativeLevel = (
        RepresentativeLevel.INSUFFICIENT_INFORMATION
    )

    @property
    def confirmed_exposures(self) -> frozenset[str]:
        return frozenset().union(
            self.contact,
            self.web,
            self.device,
            self.personal_data,
            self.financial_data,
            self.authentication,
            self.financial_loss,
        )

    @property
    def active_dimensions(self) -> frozenset[str]:
        """Return every exposure dimension that contains a confirmed action."""

        dimensions = {
            "contact": self.contact,
            "web": self.web,
            "device": self.device,
            "personal_data": self.personal_data,
            "financial_data": self.financial_data,
            "authentication": self.authentication,
            "financial_loss": self.financial_loss,
        }
        return frozenset(name for name, actions in dimensions.items() if actions)

    @property
    def is_compound(self) -> bool:
        """Whether confirmed harm spans at least two exposure dimensions."""

        return len(self.harm_dimensions) >= 2

    @property
    def harm_dimensions(self) -> frozenset[str]:
        """Return material harm dimensions, excluding initial contact alone."""

        return self.active_dimensions - {"contact"}
