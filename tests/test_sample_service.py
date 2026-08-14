from pathlib import Path

from src.models import ActionStatus
from src.sample_service import load_samples

SAMPLES_PATH = Path(__file__).parents[1] / "data" / "sample_cases.json"


def test_loads_six_unique_valid_samples() -> None:
    samples = load_samples(SAMPLES_PATH)
    assert len(samples) == 6
    assert len({sample.id for sample in samples}) == len(samples)


def test_money_transfer_sample_is_confirmed() -> None:
    sample = next(sample for sample in load_samples(SAMPLES_PATH) if sample.id == "money_transferred")
    assert sample.analysis.actions["money_transferred"].status is ActionStatus.DONE


def test_ambiguous_sample_remains_unknown() -> None:
    sample = next(sample for sample in load_samples(SAMPLES_PATH) if sample.id == "ambiguous_app")
    assert sample.analysis.actions["app_installed"].status is ActionStatus.UNKNOWN
