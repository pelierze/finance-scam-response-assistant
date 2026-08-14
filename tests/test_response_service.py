import json
import tempfile
import unittest
from pathlib import Path

from src.models import (
    TRACKED_ACTIONS,
    ActionObservation,
    ActionStatus,
    StructuredAnalysis,
)
from src.response_service import compose_guides, load_guides
from src.rule_engine import assess_exposure

GUIDES_PATH = Path(__file__).parents[1] / "data" / "response_guides.json"


def assessment_with(*done_actions: str):
    actions = {name: ActionObservation(ActionStatus.NOT_MENTIONED) for name in TRACKED_ACTIONS}
    for name in done_actions:
        actions[name] = ActionObservation(ActionStatus.DONE, "테스트 근거")
    return assess_exposure(StructuredAnalysis(None, (), actions))


class ResponseServiceTests(unittest.TestCase):
    def test_store_is_valid_and_ids_are_unique(self) -> None:
        guides = load_guides(GUIDES_PATH)
        self.assertGreaterEqual(len(guides), 7)
        self.assertEqual(len({guide.action_id for guide in guides}), len(guides))

    def test_compound_harm_includes_all_required_guides(self) -> None:
        guides = compose_guides(
            assessment_with(
                "app_installed",
                "personal_info_shared",
                "auth_secret_shared",
                "money_transferred",
            ),
            load_guides(GUIDES_PATH),
        )
        ids = {guide.action_id for guide in guides}
        self.assertTrue(
            {
                "TRANSFER_01",
                "DEVICE_EXPOSURE_01",
                "PERSONAL_DATA_01",
                "AUTH_EXPOSURE_01",
                "EVIDENCE_01",
            }
            <= ids
        )
        priorities = [guide.priority for guide in guides]
        self.assertEqual(priorities, sorted(priorities, key={"IMMEDIATE": 0, "NEXT": 1, "EVIDENCE": 2, "PREVENTION": 3}.get))

    def test_no_exposure_produces_no_specific_guides(self) -> None:
        self.assertEqual(compose_guides(assessment_with(), load_guides(GUIDES_PATH)), ())

    def test_rejects_duplicate_ids(self) -> None:
        raw = json.loads(GUIDES_PATH.read_text(encoding="utf-8"))
        raw.append(raw[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guides.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be unique"):
                load_guides(path)


if __name__ == "__main__":
    unittest.main()
