import unittest

from src.models import (
    TRACKED_ACTIONS,
    ActionObservation,
    ActionStatus,
    RepresentativeLevel,
    StructuredAnalysis,
)
from src.rule_engine import assess_exposure


def analysis_with(**statuses: ActionStatus) -> StructuredAnalysis:
    actions = {
        name: ActionObservation(ActionStatus.NOT_MENTIONED) for name in TRACKED_ACTIONS
    }
    for name, status in statuses.items():
        evidence = "테스트 근거" if status is ActionStatus.DONE else None
        actions[name] = ActionObservation(status, evidence)
    return StructuredAnalysis(None, (), actions)


class RuleEngineTests(unittest.TestCase):
    def test_requested_action_does_not_raise_level(self) -> None:
        result = assess_exposure(
            analysis_with(
                suspicious_contact_received=ActionStatus.DONE,
                app_installed=ActionStatus.REQUESTED,
            )
        )
        self.assertEqual(result.representative_level, RepresentativeLevel.SUSPICIOUS_CONTACT)
        self.assertFalse(result.device)

    def test_preserves_every_dimension_for_compound_harm(self) -> None:
        result = assess_exposure(
            analysis_with(
                link_clicked=ActionStatus.DONE,
                app_installed=ActionStatus.DONE,
                personal_info_shared=ActionStatus.DONE,
                auth_secret_shared=ActionStatus.DONE,
                money_transferred=ActionStatus.DONE,
            )
        )
        self.assertEqual(result.representative_level, RepresentativeLevel.FINANCIAL_LOSS)
        self.assertEqual(len(result.confirmed_exposures), 5)
        self.assertIn("app_installed", result.device)
        self.assertIn("auth_secret_shared", result.authentication)
        self.assertTrue(result.is_compound)
        self.assertEqual(
            result.active_dimensions,
            frozenset({"web", "device", "personal_data", "authentication", "financial_loss"}),
        )
        self.assertEqual(result.harm_dimensions, result.active_dimensions)

    def test_single_dimension_is_not_compound(self) -> None:
        result = assess_exposure(
            analysis_with(app_installed=ActionStatus.DONE)
        )
        self.assertFalse(result.is_compound)

    def test_contact_is_not_counted_as_a_material_harm_dimension(self) -> None:
        result = assess_exposure(
            analysis_with(
                suspicious_contact_received=ActionStatus.DONE,
                app_installed=ActionStatus.DONE,
            )
        )
        self.assertEqual(result.active_dimensions, frozenset({"contact", "device"}))
        self.assertEqual(result.harm_dimensions, frozenset({"device"}))
        self.assertFalse(result.is_compound)

    def test_no_confirmed_action_means_insufficient_information(self) -> None:
        result = assess_exposure(analysis_with())
        self.assertEqual(
            result.representative_level,
            RepresentativeLevel.INSUFFICIENT_INFORMATION,
        )
        self.assertFalse(result.confirmed_exposures)


if __name__ == "__main__":
    unittest.main()
