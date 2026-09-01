from datetime import UTC, datetime

from src.evaluation_metadata import build_evaluation_metadata


def test_evaluation_metadata_is_reproducible_except_for_timestamp() -> None:
    cases = [{"id": "CASE-001", "input": "주민번호 900101-1234567"}]
    guide_labels = {
        "CASE-001": {
            "required": frozenset({"PERSONAL_DATA_01"}),
            "forbidden": frozenset(),
        }
    }

    metadata = build_evaluation_metadata(
        extractor="openai",
        model="test-model",
        temperature=0,
        max_attempts=2,
        cases=cases,
        guide_labels=guide_labels,
        started_at=datetime(2026, 8, 24, 12, 0, tzinfo=UTC),
    )

    assert metadata["started_at"] == "2026-08-24T12:00:00+00:00"
    assert metadata["provider"] == "openai"
    assert metadata["api_path"] == "responses.parse"
    assert metadata["model"] == "test-model"
    assert metadata["temperature"] == 0
    assert metadata["case_count"] == 1
    assert metadata["guide_label_case_count"] == 1
    assert all(
        len(metadata[field]) == 64
        for field in (
            "system_prompt_sha256",
            "schema_sha256",
            "case_set_sha256",
            "guide_labels_sha256",
        )
    )
