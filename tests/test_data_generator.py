import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data_generator import (
    EXPECTED_COLUMNS,
    DataValidationError,
    GenerationConfig,
    choose_transcript_and_sentiment,
    collect_validation_errors,
    generate_agents,
    generate_calls_and_transcripts,
    generate_dataset,
    generate_timeoff,
    main,
    validate_generated_data,
    write_dataset,
)


def small_config(tmp_path: Path, *, seed: int = 42) -> GenerationConfig:
    return GenerationConfig(
        num_agents=6,
        start_date=date(2026, 2, 1),
        num_days=8,
        seed=seed,
        output_dir=tmp_path,
        at_risk_fraction=0.50,
        pressure_event_probability=0.25,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("num_agents", 0),
        ("num_days", 0),
        ("at_risk_fraction", -0.01),
        ("at_risk_fraction", 1.01),
        ("pressure_event_probability", -0.01),
        ("pressure_event_probability", 1.01),
    ],
)
def test_generation_config_rejects_invalid_values(field: str, value: float) -> None:
    values = {field: value}

    with pytest.raises(ValueError):
        GenerationConfig(**values)


def test_generate_agents_has_required_columns_and_unique_ids() -> None:
    agents = generate_agents(num_agents=5)

    assert len(agents) == 5
    assert EXPECTED_COLUMNS["agents"] == set(agents.columns)
    assert agents["agent_id"].is_unique
    assert agents["agent_id"].tolist() == [1, 2, 3, 4, 5]
    assert agents["baseline_calls_per_day"].between(25, 54).all()


def test_timeoff_has_one_valid_record_per_agent() -> None:
    agents = generate_agents(num_agents=4)
    timeoff = generate_timeoff(agents)

    assert len(timeoff) == len(agents)
    assert timeoff["timeoff_id"].is_unique
    assert set(timeoff["agent_id"]) == set(agents["agent_id"])
    assert timeoff["pto_balance_hours"].between(0, 119).all()
    assert timeoff["vacation_days_available"].between(0, 14).all()
    assert timeoff["pto_used_hours_30d"].between(0, 31).all()


def test_same_configuration_produces_identical_tables(tmp_path: Path) -> None:
    config = small_config(tmp_path)
    first_run = generate_dataset(config)
    second_run = generate_dataset(config)

    assert first_run.keys() == second_run.keys()
    for table_name in first_run:
        pd.testing.assert_frame_equal(first_run[table_name], second_run[table_name])


def test_different_seeds_change_the_dataset(tmp_path: Path) -> None:
    first_run = generate_dataset(small_config(tmp_path / "one", seed=42))
    second_run = generate_dataset(small_config(tmp_path / "two", seed=43))

    assert not first_run["agents"].equals(second_run["agents"])
    assert not first_run["daily_labels"].equals(second_run["daily_labels"])


def test_dataset_schema_ranges_and_relationships_are_valid(tmp_path: Path) -> None:
    tables = generate_dataset(small_config(tmp_path))

    assert collect_validation_errors(tables) == []
    validate_generated_data(tables)
    assert set(tables) == set(EXPECTED_COLUMNS)
    assert len(tables["daily_labels"]) == 6 * 8
    assert tables["daily_labels"]["latent_pressure_score"].between(0, 1).all()
    assert tables["daily_labels"]["synthetic_stress_label"].isin([0, 1]).all()
    assert set(tables["calls"]["call_id"]) == set(tables["transcripts"]["call_id"])
    assert set(tables["calls"]["transcript_id"]) == set(
        tables["transcripts"]["transcript_id"]
    )


def test_validation_reports_an_orphan_call(tmp_path: Path) -> None:
    tables = generate_dataset(small_config(tmp_path))
    tables["calls"] = tables["calls"].copy()
    tables["calls"].loc[0, "agent_id"] = 999_999

    with pytest.raises(DataValidationError, match="missing from agents"):
        validate_generated_data(tables)


def test_high_pressure_creates_more_calls_than_low_pressure() -> None:
    agents = pd.DataFrame(
        [
            {
                "agent_id": 1,
                "name": "Demo Agent",
                "team": "Billing",
                "role": "Customer Service Agent",
                "start_date": date(2025, 1, 1),
                "baseline_calls_per_day": 40,
                "baseline_avg_acw": 120,
                "baseline_avg_call_duration": 400,
            }
        ]
    )
    label_date = date(2026, 1, 1)
    low_labels = pd.DataFrame(
        [{"agent_id": 1, "label_date": label_date, "latent_pressure_score": 0.10}]
    )
    high_labels = pd.DataFrame(
        [{"agent_id": 1, "label_date": label_date, "latent_pressure_score": 0.90}]
    )

    low_calls, _ = generate_calls_and_transcripts(
        agents,
        start_date=label_date,
        num_days=1,
        daily_labels_df=low_labels,
        rng=np.random.default_rng(7),
    )
    high_calls, _ = generate_calls_and_transcripts(
        agents,
        start_date=label_date,
        num_days=1,
        daily_labels_df=high_labels,
        rng=np.random.default_rng(7),
    )

    assert len(high_calls) > len(low_calls)


def test_sentiment_bands_match_call_difficulty() -> None:
    cases = [
        (0.10, "Positive", (0.35, 1.0)),
        (0.60, "Neutral", (-0.25, 0.25)),
        (0.90, "Negative", (-1.0, -0.35)),
    ]

    for difficulty, expected_label, score_range in cases:
        text, label, score, keyword_count = choose_transcript_and_sentiment(difficulty)

        assert text
        assert label == expected_label
        assert score_range[0] <= score <= score_range[1]
        assert keyword_count >= 0


def test_write_dataset_creates_csvs_and_manifest(tmp_path: Path) -> None:
    config = small_config(tmp_path)
    tables = generate_dataset(config)
    manifest_path = write_dataset(tables, config)
    manifest = json.loads(manifest_path.read_text())

    expected_files = {
        "agents.csv",
        "timeoff.csv",
        "calls.csv",
        "transcripts.csv",
        "daily_labels.csv",
        "generation_manifest.json",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected_files
    assert manifest["schema_version"] == 1
    assert manifest["synthetic_only"] is True
    assert manifest["configuration"]["seed"] == 42
    assert manifest["row_counts"] == {name: len(table) for name, table in tables.items()}


def test_cli_accepts_custom_values_and_writes_output(tmp_path: Path) -> None:
    exit_code = main(
        [
            "--num-agents",
            "3",
            "--start-date",
            "2026-03-10",
            "--num-days",
            "2",
            "--seed",
            "99",
            "--output-dir",
            str(tmp_path),
            "--at-risk-fraction",
            "0.34",
            "--pressure-event-probability",
            "0.20",
        ]
    )
    manifest = json.loads((tmp_path / "generation_manifest.json").read_text())

    assert exit_code == 0
    assert manifest["configuration"]["num_agents"] == 3
    assert manifest["configuration"]["num_days"] == 2
    assert manifest["configuration"]["start_date"] == "2026-03-10"
    assert manifest["row_counts"]["daily_labels"] == 6
