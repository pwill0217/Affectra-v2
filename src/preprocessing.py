"""Clean Affectra CSV inputs and produce a transparent data-quality report."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data_generator import EXPECTED_COLUMNS, TABLE_FILENAMES
from src.data_loader import load_raw_tables, validate_required_columns

DATE_COLUMNS = {
    "agents": ["start_date"],
    "timeoff": ["last_pto_date"],
    "calls": ["call_date"],
    "daily_labels": ["label_date"],
}

INTEGER_COLUMNS = {
    "agents": [
        "agent_id",
        "baseline_calls_per_day",
        "baseline_avg_acw",
        "baseline_avg_call_duration",
    ],
    "timeoff": [
        "timeoff_id",
        "agent_id",
        "pto_balance_hours",
        "vacation_days_available",
        "pto_used_hours_30d",
    ],
    "calls": [
        "call_id",
        "agent_id",
        "duration_seconds",
        "acw_seconds",
        "hold_seconds",
        "transfer_count",
        "transcript_id",
    ],
    "transcripts": [
        "transcript_id",
        "call_id",
        "negative_keyword_count",
    ],
    "daily_labels": ["agent_id", "synthetic_stress_label"],
}

FLOAT_COLUMNS = {
    "transcripts": ["sentiment_score"],
    "daily_labels": ["latent_pressure_score"],
}

TEXT_COLUMNS = {
    "agents": ["name", "team", "role"],
    "transcripts": ["transcript_text", "sentiment_label"],
    "daily_labels": ["pressure_band"],
}

BOOLEAN_COLUMNS = {"daily_labels": ["simulated_pressure_event"]}

PRIMARY_KEYS = {
    "agents": ["agent_id"],
    "timeoff": ["timeoff_id"],
    "calls": ["call_id"],
    "transcripts": ["transcript_id"],
    "daily_labels": ["agent_id", "label_date"],
}

SECONDARY_UNIQUE_KEYS = {
    "timeoff": [["agent_id"]],
    "calls": [["transcript_id"]],
    "transcripts": [["call_id"]],
}

CRITICAL_COLUMNS = {
    "agents": ["agent_id"],
    "timeoff": ["timeoff_id", "agent_id"],
    "calls": ["call_id", "agent_id", "call_date", "transcript_id"],
    "transcripts": ["transcript_id", "call_id"],
    "daily_labels": ["agent_id", "label_date", "synthetic_stress_label"],
}

NUMERIC_BOUNDS: dict[str, dict[str, tuple[float | None, float | None]]] = {
    "agents": {
        "agent_id": (1, None),
        "baseline_calls_per_day": (1, None),
        "baseline_avg_acw": (0, None),
        "baseline_avg_call_duration": (1, None),
    },
    "timeoff": {
        "timeoff_id": (1, None),
        "agent_id": (1, None),
        "pto_balance_hours": (0, None),
        "vacation_days_available": (0, None),
        "pto_used_hours_30d": (0, None),
    },
    "calls": {
        "call_id": (1, None),
        "agent_id": (1, None),
        "duration_seconds": (120, None),
        "acw_seconds": (30, None),
        "hold_seconds": (0, None),
        "transcript_id": (1, None),
    },
    "transcripts": {
        "transcript_id": (1, None),
        "call_id": (1, None),
        "sentiment_score": (-1, 1),
        "negative_keyword_count": (0, None),
    },
    "daily_labels": {
        "agent_id": (1, None),
        "latent_pressure_score": (0, 1),
    },
}

ALLOWED_VALUES = {
    ("calls", "transfer_count"): {0, 1, 2, 3},
    ("transcripts", "sentiment_label"): {"Positive", "Neutral", "Negative"},
    ("daily_labels", "pressure_band"): {"Low", "Elevated", "High"},
    ("daily_labels", "synthetic_stress_label"): {0, 1},
}

OUTLIER_COLUMNS = {
    "agents": [
        "baseline_calls_per_day",
        "baseline_avg_acw",
        "baseline_avg_call_duration",
    ],
    "timeoff": ["pto_balance_hours", "vacation_days_available", "pto_used_hours_30d"],
    "calls": ["duration_seconds", "acw_seconds", "hold_seconds"],
    "transcripts": ["sentiment_score", "negative_keyword_count"],
    "daily_labels": ["latent_pressure_score"],
}


class DataQualityError(ValueError):
    """Raised when cleaning cannot produce a usable set of related tables."""


@dataclass(frozen=True)
class PreprocessingConfig:
    """Settings for one preprocessing run."""

    input_dir: Path = Path("data/synthetic")
    output_dir: Path = Path("data/processed")
    iqr_multiplier: float = 1.5

    def __post_init__(self) -> None:
        if self.iqr_multiplier <= 0:
            raise ValueError("iqr_multiplier must be greater than 0")


def _missing_counts(dataframe: pd.DataFrame, columns: set[str]) -> dict[str, int]:
    return {
        column: int(dataframe[column].isna().sum())
        for column in sorted(columns)
        if dataframe[column].isna().any()
    }


def _record_count(report_section: dict[str, Any], key: str, count: int) -> None:
    if count:
        report_section[key] = int(count)


def _coerce_boolean(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return pd.NA


def _coerce_types(
    table_name: str,
    dataframe: pd.DataFrame,
    report: dict[str, Any],
) -> pd.DataFrame:
    cleaned = dataframe.copy()

    for column in INTEGER_COLUMNS.get(table_name, []):
        original_missing = cleaned[column].isna()
        converted = pd.to_numeric(cleaned[column], errors="coerce")
        _record_count(
            report["invalid_values_coerced"],
            column,
            int((~original_missing & converted.isna()).sum()),
        )
        cleaned[column] = converted

    for column in FLOAT_COLUMNS.get(table_name, []):
        original_missing = cleaned[column].isna()
        converted = pd.to_numeric(cleaned[column], errors="coerce")
        _record_count(
            report["invalid_values_coerced"],
            column,
            int((~original_missing & converted.isna()).sum()),
        )
        cleaned[column] = converted

    for column in DATE_COLUMNS.get(table_name, []):
        original_missing = cleaned[column].isna()
        converted = pd.to_datetime(cleaned[column], errors="coerce", format="ISO8601")
        _record_count(
            report["invalid_values_coerced"],
            column,
            int((~original_missing & converted.isna()).sum()),
        )
        cleaned[column] = converted

    for column in TEXT_COLUMNS.get(table_name, []):
        original = cleaned[column]
        normalized = original.map(lambda value: value.strip() if isinstance(value, str) else value)
        cleaned[column] = normalized.replace("", pd.NA)

    for column in BOOLEAN_COLUMNS.get(table_name, []):
        original_missing = cleaned[column].isna()
        converted = cleaned[column].map(_coerce_boolean)
        _record_count(
            report["invalid_values_coerced"],
            column,
            int((~original_missing & converted.isna()).sum()),
        )
        cleaned[column] = converted

    return cleaned


def _replace_invalid_ranges(
    table_name: str,
    dataframe: pd.DataFrame,
    report: dict[str, Any],
) -> pd.DataFrame:
    cleaned = dataframe.copy()

    for column, (minimum, maximum) in NUMERIC_BOUNDS.get(table_name, {}).items():
        invalid = pd.Series(False, index=cleaned.index)
        if minimum is not None:
            invalid |= cleaned[column].notna() & cleaned[column].lt(minimum)
        if maximum is not None:
            invalid |= cleaned[column].notna() & cleaned[column].gt(maximum)
        _record_count(report["invalid_range_values"], column, int(invalid.sum()))
        cleaned.loc[invalid, column] = np.nan

    for (allowed_table, column), allowed_values in ALLOWED_VALUES.items():
        if allowed_table != table_name:
            continue
        invalid = cleaned[column].notna() & ~cleaned[column].isin(allowed_values)
        _record_count(report["invalid_range_values"], column, int(invalid.sum()))
        cleaned.loc[invalid, column] = pd.NA

    return cleaned


def _drop_duplicate_keys(
    table_name: str,
    dataframe: pd.DataFrame,
    report: dict[str, Any],
) -> pd.DataFrame:
    cleaned = dataframe.copy()
    exact_duplicates = cleaned.duplicated(keep="first")
    report["exact_duplicates_removed"] = int(exact_duplicates.sum())
    cleaned = cleaned.loc[~exact_duplicates].copy()

    key_sets = [PRIMARY_KEYS[table_name], *SECONDARY_UNIQUE_KEYS.get(table_name, [])]
    key_duplicates_removed = 0
    for key_columns in key_sets:
        duplicate_keys = cleaned.duplicated(key_columns, keep="first")
        key_duplicates_removed += int(duplicate_keys.sum())
        cleaned = cleaned.loc[~duplicate_keys].copy()
    report["duplicate_key_rows_removed"] = key_duplicates_removed
    return cleaned


def _drop_missing_critical_rows(
    table_name: str,
    dataframe: pd.DataFrame,
    report: dict[str, Any],
) -> pd.DataFrame:
    missing_critical = dataframe[CRITICAL_COLUMNS[table_name]].isna().any(axis=1)
    report["rows_dropped_for_missing_keys"] = int(missing_critical.sum())
    return dataframe.loc[~missing_critical].copy()


def _impute_known_values(
    table_name: str,
    dataframe: pd.DataFrame,
    report: dict[str, Any],
) -> pd.DataFrame:
    cleaned = dataframe.copy()
    critical = set(CRITICAL_COLUMNS[table_name])

    numeric_columns = INTEGER_COLUMNS.get(table_name, []) + FLOAT_COLUMNS.get(table_name, [])
    for column in numeric_columns:
        if column in critical:
            continue
        missing_count = int(cleaned[column].isna().sum())
        if not missing_count:
            continue
        median = cleaned[column].median()
        if pd.isna(median):
            median = 0
        cleaned[column] = cleaned[column].fillna(median)
        report["values_imputed"][column] = {
            "count": missing_count,
            "strategy": "median",
            "value": float(median),
        }

    for column in TEXT_COLUMNS.get(table_name, []):
        missing_count = int(cleaned[column].isna().sum())
        if not missing_count:
            continue
        modes = cleaned[column].mode(dropna=True)
        fill_value = str(modes.iloc[0]) if not modes.empty else "Unknown"
        cleaned[column] = cleaned[column].fillna(fill_value)
        report["values_imputed"][column] = {
            "count": missing_count,
            "strategy": "mode" if not modes.empty else "fallback",
            "value": fill_value,
        }

    for column in BOOLEAN_COLUMNS.get(table_name, []):
        missing_count = int(cleaned[column].isna().sum())
        if not missing_count:
            continue
        modes = cleaned[column].mode(dropna=True)
        fill_value = bool(modes.iloc[0]) if not modes.empty else False
        cleaned[column] = cleaned[column].fillna(fill_value)
        report["values_imputed"][column] = {
            "count": missing_count,
            "strategy": "mode" if not modes.empty else "fallback",
            "value": fill_value,
        }

    for column in DATE_COLUMNS.get(table_name, []):
        if column in critical:
            continue
        missing_count = int(cleaned[column].isna().sum())
        if not missing_count:
            continue
        median = cleaned[column].median()
        if pd.isna(median):
            continue
        cleaned[column] = cleaned[column].fillna(median)
        report["values_imputed"][column] = {
            "count": missing_count,
            "strategy": "median_date",
            "value": pd.Timestamp(median).date().isoformat(),
        }

    return cleaned


def _set_output_dtypes(table_name: str, dataframe: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataframe.copy()
    for column in INTEGER_COLUMNS.get(table_name, []):
        cleaned[column] = cleaned[column].round().astype("Int64")
    for column in FLOAT_COLUMNS.get(table_name, []):
        cleaned[column] = cleaned[column].astype(float)
    for column in BOOLEAN_COLUMNS.get(table_name, []):
        cleaned[column] = cleaned[column].astype("boolean")
    for column in DATE_COLUMNS.get(table_name, []):
        cleaned[column] = pd.to_datetime(cleaned[column]).dt.normalize()
    return cleaned.reset_index(drop=True)


def clean_table(
    table_name: str,
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply type, range, duplicate, missing-value, and dtype policies."""
    report: dict[str, Any] = {
        "input_rows": len(dataframe),
        "output_rows": 0,
        "extra_columns": sorted(set(dataframe.columns) - EXPECTED_COLUMNS[table_name]),
        "missing_before": _missing_counts(dataframe, EXPECTED_COLUMNS[table_name]),
        "invalid_values_coerced": {},
        "invalid_range_values": {},
        "exact_duplicates_removed": 0,
        "duplicate_key_rows_removed": 0,
        "rows_dropped_for_missing_keys": 0,
        "values_imputed": {},
        "orphan_rows_removed": 0,
        "missing_after": {},
        "outliers": {},
    }
    cleaned = _coerce_types(table_name, dataframe, report)
    cleaned = _replace_invalid_ranges(table_name, cleaned, report)
    cleaned = _drop_missing_critical_rows(table_name, cleaned, report)
    cleaned = _drop_duplicate_keys(table_name, cleaned, report)
    cleaned = _impute_known_values(table_name, cleaned, report)
    cleaned = _set_output_dtypes(table_name, cleaned)
    report["output_rows"] = len(cleaned)
    report["missing_after"] = _missing_counts(cleaned, EXPECTED_COLUMNS[table_name])
    return cleaned, report


def _drop_orphans(
    cleaned: dict[str, pd.DataFrame],
    table_reports: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    relationships: dict[str, Any] = {}
    agent_ids = set(cleaned["agents"]["agent_id"].astype(int))

    for table_name in ["timeoff", "calls", "daily_labels"]:
        valid_agent = cleaned[table_name]["agent_id"].astype(int).isin(agent_ids)
        removed = int((~valid_agent).sum())
        cleaned[table_name] = cleaned[table_name].loc[valid_agent].reset_index(drop=True)
        table_reports[table_name]["orphan_rows_removed"] += removed
        relationships[f"{table_name}_orphan_agents_removed"] = removed

    call_pairs = set(
        zip(cleaned["calls"]["call_id"], cleaned["calls"]["transcript_id"], strict=True)
    )
    transcript_pairs = set(
        zip(
            cleaned["transcripts"]["call_id"],
            cleaned["transcripts"]["transcript_id"],
            strict=True,
        )
    )
    valid_pairs = call_pairs & transcript_pairs
    valid_call_rows = [
        (call_id, transcript_id) in valid_pairs
        for call_id, transcript_id in zip(
            cleaned["calls"]["call_id"],
            cleaned["calls"]["transcript_id"],
            strict=True,
        )
    ]
    valid_transcript_rows = [
        (call_id, transcript_id) in valid_pairs
        for call_id, transcript_id in zip(
            cleaned["transcripts"]["call_id"],
            cleaned["transcripts"]["transcript_id"],
            strict=True,
        )
    ]
    removed_calls = len(cleaned["calls"]) - sum(valid_call_rows)
    removed_transcripts = len(cleaned["transcripts"]) - sum(valid_transcript_rows)
    cleaned["calls"] = cleaned["calls"].loc[valid_call_rows].reset_index(drop=True)
    cleaned["transcripts"] = cleaned["transcripts"].loc[
        valid_transcript_rows
    ].reset_index(drop=True)
    table_reports["calls"]["orphan_rows_removed"] += removed_calls
    table_reports["transcripts"]["orphan_rows_removed"] += removed_transcripts
    relationships["unmatched_calls_removed"] = removed_calls
    relationships["unmatched_transcripts_removed"] = removed_transcripts

    expected_agent_days = len(agent_ids) * cleaned["daily_labels"]["label_date"].nunique()
    relationships["missing_agent_day_labels"] = max(
        0,
        expected_agent_days - len(cleaned["daily_labels"]),
    )
    relationships["agents_without_timeoff"] = len(
        agent_ids - set(cleaned["timeoff"]["agent_id"].astype(int))
    )

    for table_name, dataframe in cleaned.items():
        table_reports[table_name]["output_rows"] = len(dataframe)
        table_reports[table_name]["missing_after"] = _missing_counts(
            dataframe,
            EXPECTED_COLUMNS[table_name],
        )
    return relationships


def iqr_outlier_summary(
    dataframe: pd.DataFrame,
    columns: list[str],
    *,
    multiplier: float = 1.5,
) -> dict[str, dict[str, float | int]]:
    """Report IQR outliers without deleting or recursively rechecking rows."""
    if multiplier <= 0:
        raise ValueError("multiplier must be greater than 0")

    summary: dict[str, dict[str, float | int]] = {}
    for column in columns:
        values = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        if values.empty:
            continue
        first_quartile = float(values.quantile(0.25))
        third_quartile = float(values.quantile(0.75))
        iqr = third_quartile - first_quartile
        lower_bound = first_quartile - multiplier * iqr
        upper_bound = third_quartile + multiplier * iqr
        outlier_count = int(((values < lower_bound) | (values > upper_bound)).sum())
        summary[column] = {
            "q1": round(first_quartile, 4),
            "q3": round(third_quartile, 4),
            "iqr": round(iqr, 4),
            "lower_bound": round(lower_bound, 4),
            "upper_bound": round(upper_bound, 4),
            "count": outlier_count,
            "percentage": round(100 * outlier_count / len(values), 4),
        }
    return summary


def _correction_count(table_report: dict[str, Any]) -> int:
    return (
        sum(table_report["invalid_values_coerced"].values())
        + sum(table_report["invalid_range_values"].values())
        + table_report["exact_duplicates_removed"]
        + table_report["duplicate_key_rows_removed"]
        + table_report["rows_dropped_for_missing_keys"]
        + sum(details["count"] for details in table_report["values_imputed"].values())
        + table_report["orphan_rows_removed"]
    )


def preprocess_tables(
    raw_tables: dict[str, pd.DataFrame],
    *,
    iqr_multiplier: float = 1.5,
    input_dir: Path | str = "data/synthetic",
    output_dir: Path | str = "data/processed",
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Clean all tables, enforce relationships, and build a quality report."""
    if iqr_multiplier <= 0:
        raise ValueError("iqr_multiplier must be greater than 0")
    validate_required_columns(raw_tables)

    cleaned: dict[str, pd.DataFrame] = {}
    table_reports: dict[str, dict[str, Any]] = {}
    for table_name in EXPECTED_COLUMNS:
        cleaned[table_name], table_reports[table_name] = clean_table(
            table_name,
            raw_tables[table_name],
        )

    relationships = _drop_orphans(cleaned, table_reports)
    for table_name, columns in OUTLIER_COLUMNS.items():
        table_reports[table_name]["outliers"] = iqr_outlier_summary(
            cleaned[table_name],
            columns,
            multiplier=iqr_multiplier,
        )

    empty_tables = [name for name, table in cleaned.items() if table.empty]
    if empty_tables:
        raise DataQualityError(
            "Cleaning left required tables empty: " + ", ".join(sorted(empty_tables))
        )

    total_corrections = sum(_correction_count(report) for report in table_reports.values())
    total_outliers = sum(
        details["count"]
        for report in table_reports.values()
        for details in report["outliers"].values()
    )
    relationship_warnings = relationships["missing_agent_day_labels"] + relationships[
        "agents_without_timeoff"
    ]
    report = {
        "report_version": 1,
        "source_schema_version": 1,
        "status": (
            "passed_with_warnings"
            if total_corrections or total_outliers or relationship_warnings
            else "passed"
        ),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "policy": {
            "missing_markers": ["?", "-", "N/A"],
            "critical_missing_rows": "drop",
            "numeric_missing_values": "median imputation",
            "text_and_boolean_missing_values": "mode imputation",
            "noncritical_missing_dates": "median-date imputation",
            "duplicate_rows_and_keys": "keep first",
            "orphan_relationships": "drop child row",
            "outliers": "report only; preserve values",
            "iqr_multiplier": iqr_multiplier,
        },
        "tables": table_reports,
        "relationships": relationships,
        "totals": {
            "input_rows": sum(len(table) for table in raw_tables.values()),
            "output_rows": sum(len(table) for table in cleaned.values()),
            "corrections": total_corrections,
            "outliers_reported": total_outliers,
            "relationship_warnings": relationship_warnings,
        },
    }
    return cleaned, report


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_processed_outputs(
    cleaned_tables: dict[str, pd.DataFrame],
    quality_report: dict[str, Any],
    output_dir: Path | str,
) -> Path:
    """Write cleaned CSVs and the machine-readable quality report."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    for table_name, filename in TABLE_FILENAMES.items():
        cleaned_tables[table_name].to_csv(output_path / filename, index=False)

    report_path = output_path / "data_quality_report.json"
    report_path.write_text(
        json.dumps(quality_report, indent=2, sort_keys=True, default=_json_default) + "\n"
    )
    return report_path


def run_preprocessing(
    config: PreprocessingConfig,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Load, clean, report, and write one complete preprocessing run."""
    raw_tables = load_raw_tables(config.input_dir)
    cleaned_tables, quality_report = preprocess_tables(
        raw_tables,
        iqr_multiplier=config.iqr_multiplier,
        input_dir=config.input_dir,
        output_dir=config.output_dir,
    )
    write_processed_outputs(cleaned_tables, quality_report, config.output_dir)
    return cleaned_tables, quality_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--iqr-multiplier", type=float, default=1.5)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run preprocessing from a terminal command."""
    args = build_parser().parse_args(argv)
    config = PreprocessingConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        iqr_multiplier=args.iqr_multiplier,
    )
    cleaned_tables, quality_report = run_preprocessing(config)

    print("Affectra data loaded, cleaned, validated, and written.")
    for table_name, table in cleaned_tables.items():
        print(f"{table_name}: {len(table):,} cleaned rows")
    print(f"Status: {quality_report['status']}")
    print(f"Corrections: {quality_report['totals']['corrections']:,}")
    print(f"Outliers reported: {quality_report['totals']['outliers_reported']:,}")
    print(f"Quality report: {config.output_dir / 'data_quality_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
