from pathlib import Path

from src.models import ActionStatus
from src.response_service import compose_guides, load_guides
from src.rule_engine import assess_exposure
from src.sample_service import load_samples

SAMPLES_PATH = Path(__file__).parents[1] / "data" / "sample_cases.json"
GUIDES_PATH = Path(__file__).parents[1] / "data" / "response_guides.json"


def test_loads_seven_unique_valid_samples() -> None:
    samples = load_samples(SAMPLES_PATH)
    assert len(samples) == 7
    assert len({sample.id for sample in samples}) == len(samples)


def test_money_transfer_sample_is_confirmed() -> None:
    sample = next(sample for sample in load_samples(SAMPLES_PATH) if sample.id == "money_transferred")
    assert sample.analysis.actions["money_transferred"].status is ActionStatus.DONE


def test_ambiguous_sample_remains_unknown() -> None:
    sample = next(sample for sample in load_samples(SAMPLES_PATH) if sample.id == "ambiguous_app")
    assert sample.analysis.actions["app_installed"].status is ActionStatus.UNKNOWN


def test_compound_sample_confirms_all_three_harm_types() -> None:
    sample = next(
        sample for sample in load_samples(SAMPLES_PATH) if sample.id == "compound_harm"
    )
    assert sample.analysis.actions["app_installed"].status is ActionStatus.DONE
    assert sample.analysis.actions["auth_secret_shared"].status is ActionStatus.DONE
    assert sample.analysis.actions["money_transferred"].status is ActionStatus.DONE


def test_every_sample_matches_expected_level_and_required_guides() -> None:
    guides = load_guides(GUIDES_PATH)
    for sample in load_samples(SAMPLES_PATH):
        assessment = assess_exposure(sample.analysis)
        selected_ids = {
            guide.action_id for guide in compose_guides(assessment, guides)
        }
        assert int(assessment.representative_level) == sample.expected_level, sample.id
        assert sample.required_guide_ids <= selected_ids, sample.id
