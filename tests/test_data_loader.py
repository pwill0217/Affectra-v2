"""Tests for Affectra's CSV ingestion boundary."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.data_generator import (
    EXPECTED_COLUMNS,
    TABLE_FILENAMES,
    GenerationConfig,
    generate_dataset,
    write_dataset,
)
from src.data_loader import DataLoadError, find_input_files, load_raw_tables


def write_small_dataset(output_dir: Path) -> dict[str, pd.DataFrame]:
    config = GenerationConfig(
        num_agents=4,
        start_date=date(2026, 4, 1),
        num_days=3,
        seed=17,
        output_dir=output_dir,
    )
    tables = generate_dataset(config)
    write_dataset(tables, config)
    return tables


def test_load_raw_tables_reads_all_tables_and_preserves_untrusted_types(
    tmp_path: Path,
) -> None:
    write_small_dataset(tmp_path)

    loaded = load_raw_tables(tmp_path)

    assert set(loaded) == set(EXPECTED_COLUMNS)
    assert all(set(loaded[name].columns) >= columns for name, columns in EXPECTED_COLUMNS.items())
    assert loaded["agents"]["agent_id"].dtype == object


def test_loader_reports_every_missing_required_file(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)

    with pytest.raises(DataLoadError) as error:
        find_input_files(tmp_path)

    message = str(error.value)
    assert "Required CSV files are missing" in message
    for filename in TABLE_FILENAMES.values():
        assert filename in message


def test_loader_rejects_missing_input_directory_and_file_path(tmp_path: Path) -> None:
    with pytest.raises(DataLoadError, match="does not exist"):
        find_input_files(tmp_path / "missing")

    input_file = tmp_path / "not-a-directory.csv"
    input_file.write_text("value\n1\n")
    with pytest.raises(DataLoadError, match="not a directory"):
        find_input_files(input_file)


def test_loader_reports_missing_required_columns(tmp_path: Path) -> None:
    write_small_dataset(tmp_path)
    agents_path = tmp_path / TABLE_FILENAMES["agents"]
    agents = pd.read_csv(agents_path).drop(columns="team")
    agents.to_csv(agents_path, index=False)

    with pytest.raises(DataLoadError, match="agents is missing columns: team"):
        load_raw_tables(tmp_path)


def test_loader_normalizes_documented_missing_markers_and_allows_extra_columns(
    tmp_path: Path,
) -> None:
    write_small_dataset(tmp_path)
    agents_path = tmp_path / TABLE_FILENAMES["agents"]
    agents = pd.read_csv(agents_path, dtype=object)
    agents.loc[0, "team"] = "?"
    agents.loc[1, "role"] = "-"
    agents.loc[2, "name"] = "N/A"
    agents["source_note"] = "test fixture"
    agents.to_csv(agents_path, index=False)

    loaded = load_raw_tables(tmp_path)

    assert loaded["agents"].loc[0, "team"] is pd.NA or pd.isna(
        loaded["agents"].loc[0, "team"]
    )
    assert pd.isna(loaded["agents"].loc[1, "role"])
    assert pd.isna(loaded["agents"].loc[2, "name"])
    assert "source_note" in loaded["agents"].columns
