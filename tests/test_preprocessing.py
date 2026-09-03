"""Tests for cleaning, relationship checks, reporting, and the Sprint 2 CLI."""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.data_generator import TABLE_FILENAMES, GenerationConfig, generate_dataset, write_dataset
from src.preprocessing import (
    DataQualityError,
    PreprocessingConfig,
    iqr_outlier_summary,
    main,
    preprocess_tables,
    run_preprocessing,
)


def small_tables(output_dir: Path, *, seed: int = 23) -> dict[str, pd.DataFrame]:
    config = GenerationConfig(
        num_agents=5,
        start_date=date(2026, 5, 1),
        num_days=4,
        seed=seed,
        output_dir=output_dir,
    )
    tables = generate_dataset(config)
    write_dataset(tables, config)
    return tables


def test_valid_pipeline_writes_typed_tables_and_json_report(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "processed"
    source_tables = small_tables(input_dir)

    cleaned, report = run_preprocessing(PreprocessingConfig(input_dir, output_dir))

    assert set(cleaned) == set(TABLE_FILENAMES)
    assert report["status"] in {"passed", "passed_with_warnings"}
    assert report["totals"]["input_rows"] == sum(len(table) for table in source_tables.values())
    assert str(cleaned["agents"]["agent_id"].dtype) == "Int64"
    assert pd.api.types.is_datetime64_any_dtype(cleaned["calls"]["call_date"])
    assert cleaned["calls"]["call_id"].is_unique
    assert set(cleaned["calls"]["call_id"]) == set(cleaned["transcripts"]["call_id"])

    expected_files = set(TABLE_FILENAMES.values()) | {"data_quality_report.json"}
    assert {path.name for path in output_dir.iterdir()} == expected_files
    saved_report = json.loads((output_dir / "data_quality_report.json").read_text())
    assert saved_report["policy"]["outliers"] == "report only; preserve values"


def test_broken_fixture_is_cleaned_and_each_problem_is_reported(tmp_path: Path) -> None:
    raw = small_tables(tmp_path / "source")

    raw["agents"] = raw["agents"].astype(object)
    raw["agents"].loc[0, "baseline_avg_acw"] = "not-a-number"
    duplicate_agent = raw["agents"].iloc[[1]].copy()
    duplicate_agent.loc[:, "name"] = "Duplicate Key"
    raw["agents"] = pd.concat([raw["agents"], duplicate_agent], ignore_index=True)

    raw["timeoff"] = raw["timeoff"].astype(object)
    raw["timeoff"].loc[0, "last_pto_date"] = "?"
    orphan_timeoff = raw["timeoff"].iloc[[1]].copy()
    orphan_timeoff.loc[:, "timeoff_id"] = 999
    orphan_timeoff.loc[:, "agent_id"] = 999
    raw["timeoff"] = pd.concat([raw["timeoff"], orphan_timeoff], ignore_index=True)

    raw["calls"] = raw["calls"].astype(object)
    raw["calls"].loc[0, "duration_seconds"] = 10
    raw["calls"].loc[1, "agent_id"] = 999
    raw["calls"].loc[2, "transcript_id"] = 999_999

    raw["transcripts"] = raw["transcripts"].astype(object)
    raw["transcripts"].loc[3, "negative_keyword_count"] = -4
    raw["transcripts"].loc[4, "sentiment_label"] = "Confused"

    raw["daily_labels"] = raw["daily_labels"].astype(object)
    raw["daily_labels"].loc[0, "synthetic_stress_label"] = 9
    raw["daily_labels"] = pd.concat(
        [raw["daily_labels"], raw["daily_labels"].iloc[[1]]],
        ignore_index=True,
    )

    cleaned, report = preprocess_tables(raw)

    assert report["status"] == "passed_with_warnings"
    assert report["tables"]["agents"]["invalid_values_coerced"]["baseline_avg_acw"] == 1
    assert report["tables"]["agents"]["duplicate_key_rows_removed"] == 1
    assert report["tables"]["timeoff"]["values_imputed"]["last_pto_date"]["count"] == 1
    assert report["tables"]["calls"]["invalid_range_values"]["duration_seconds"] == 1
    assert report["tables"]["daily_labels"]["rows_dropped_for_missing_keys"] == 1
    assert report["tables"]["daily_labels"]["exact_duplicates_removed"] == 1
    assert report["relationships"]["timeoff_orphan_agents_removed"] == 1
    assert report["relationships"]["unmatched_calls_removed"] >= 1
    assert report["relationships"]["unmatched_transcripts_removed"] >= 1
    assert cleaned["agents"]["baseline_avg_acw"].isna().sum() == 0
    assert cleaned["transcripts"]["negative_keyword_count"].min() >= 0
    assert set(cleaned["timeoff"]["agent_id"]) <= set(cleaned["agents"]["agent_id"])
    assert set(cleaned["calls"]["call_id"]) == set(cleaned["transcripts"]["call_id"])


def test_iqr_outliers_are_reported_without_changing_data() -> None:
    dataframe = pd.DataFrame({"metric": [1, 2, 3, 4, 100]})
    original = dataframe.copy(deep=True)

    summary = iqr_outlier_summary(dataframe, ["metric"])

    assert summary["metric"]["count"] == 1
    assert summary["metric"]["percentage"] == 20.0
    pd.testing.assert_frame_equal(dataframe, original)


@pytest.mark.parametrize("value", [0, -1])
def test_iqr_multiplier_must_be_positive(value: float) -> None:
    with pytest.raises(ValueError, match="greater than 0"):
        PreprocessingConfig(iqr_multiplier=value)
    with pytest.raises(ValueError, match="greater than 0"):
        iqr_outlier_summary(pd.DataFrame({"metric": [1]}), ["metric"], multiplier=value)


def test_pipeline_rejects_cleaning_that_leaves_required_tables_empty(tmp_path: Path) -> None:
    raw = small_tables(tmp_path)
    raw["agents"] = raw["agents"].iloc[0:0]

    with pytest.raises(DataQualityError, match="Cleaning left required tables empty"):
        preprocess_tables(raw)


def test_cli_runs_end_to_end_with_custom_directories(tmp_path: Path, capsys) -> None:
    input_dir = tmp_path / "incoming"
    output_dir = tmp_path / "outgoing"
    small_tables(input_dir)

    exit_code = main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--iqr-multiplier",
            "2.0",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "data_quality_report.json").is_file()
    assert "Affectra data loaded, cleaned, validated, and written." in capsys.readouterr().out
