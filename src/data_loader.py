"""Load Affectra CSV inputs and enforce their required schemas."""

from pathlib import Path

import pandas as pd

from src.data_generator import EXPECTED_COLUMNS, TABLE_FILENAMES

DEFAULT_MISSING_MARKERS = ["?", "-", "N/A"]


class DataLoadError(ValueError):
    """Raised when an input directory or CSV schema cannot be loaded safely."""


def find_input_files(input_dir: Path) -> dict[str, Path]:
    """Resolve all expected table paths or raise one error listing missing files."""
    if not input_dir.exists():
        raise DataLoadError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise DataLoadError(f"Input path is not a directory: {input_dir}")

    paths = {name: input_dir / filename for name, filename in TABLE_FILENAMES.items()}
    missing_files = [str(path) for path in paths.values() if not path.is_file()]
    if missing_files:
        details = "\n".join(f"- {path}" for path in missing_files)
        raise DataLoadError(f"Required CSV files are missing:\n{details}")
    return paths


def validate_required_columns(tables: dict[str, pd.DataFrame]) -> None:
    """Reject missing tables or columns while allowing documented extra columns."""
    errors: list[str] = []
    for table_name, required_columns in EXPECTED_COLUMNS.items():
        if table_name not in tables:
            errors.append(f"Missing table: {table_name}")
            continue
        missing_columns = sorted(required_columns - set(tables[table_name].columns))
        if missing_columns:
            errors.append(f"{table_name} is missing columns: {', '.join(missing_columns)}")

    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise DataLoadError(f"Input schema validation failed:\n{details}")


def load_raw_tables(
    input_dir: Path | str,
    *,
    missing_markers: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Load five CSVs as untrusted values, then verify required columns.

    Values intentionally stay as Python objects here. Type conversion belongs
    to preprocessing, where failed conversions can be counted and reported.
    """
    input_path = Path(input_dir)
    paths = find_input_files(input_path)
    markers = DEFAULT_MISSING_MARKERS if missing_markers is None else missing_markers
    tables: dict[str, pd.DataFrame] = {}
    read_errors: list[str] = []

    for table_name, path in paths.items():
        try:
            tables[table_name] = pd.read_csv(
                path,
                dtype=object,
                na_values=markers,
                keep_default_na=True,
            )
        except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
            read_errors.append(f"{path}: {error}")

    if read_errors:
        details = "\n".join(f"- {error}" for error in read_errors)
        raise DataLoadError(f"One or more CSV files could not be read:\n{details}")

    validate_required_columns(tables)
    return tables
