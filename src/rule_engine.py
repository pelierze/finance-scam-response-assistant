"""Deterministic exposure assessment from validated action observations."""

from __future__ import annotations

from src.models import (
    ActionStatus,
    ExposureAssessment,
    RepresentativeLevel,
    StructuredAnalysis,
)


def assess_exposure(analysis: StructuredAnalysis) -> ExposureAssessment:
    """Assess only confirmed actions, preserving all exposure dimensions."""

    done = {
        action
        for action, observation in analysis.actions.items()
        if observation.status is ActionStatus.DONE
    }

    contact = done & {"suspicious_contact_received"}
    web = done & {"link_clicked"}
    device = done & {"app_installed", "remote_control_enabled"}
    personal_data = done & {"personal_info_shared"}
    financial_data = done & {"financial_info_shared"}
    authentication = done & {"auth_secret_shared"}
    financial_loss = done & {"money_transferred"}

    if financial_loss:
        level = RepresentativeLevel.FINANCIAL_LOSS
    elif personal_data or financial_data or authentication:
        level = RepresentativeLevel.INFORMATION_EXPOSURE
    elif device:
        level = RepresentativeLevel.DEVICE_EXPOSURE
    elif web:
        level = RepresentativeLevel.WEB_EXPOSURE
    elif contact:
        level = RepresentativeLevel.SUSPICIOUS_CONTACT
    else:
        level = RepresentativeLevel.INSUFFICIENT_INFORMATION

    return ExposureAssessment(
        contact=frozenset(contact),
        web=frozenset(web),
        device=frozenset(device),
        personal_data=frozenset(personal_data),
        financial_data=frozenset(financial_data),
        authentication=frozenset(authentication),
        financial_loss=frozenset(financial_loss),
        representative_level=level,
    )
