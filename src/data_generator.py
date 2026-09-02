"""Generate reproducible, internally consistent synthetic data for Affectra."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

TEAMS = ["Billing", "Technical Support", "Claims", "Card Services", "General Support"]
ROLES = ["Customer Service Agent", "Senior Agent", "Escalation Specialist"]

POSITIVE_TRANSCRIPTS = [
    "Customer was polite and the agent resolved the issue quickly.",
    "The call went smoothly and the customer thanked the agent.",
    "Agent provided clear steps and the customer was satisfied.",
    "Customer had a simple question and the agent answered confidently.",
]
NEUTRAL_TRANSCRIPTS = [
    "Customer asked about account information and the agent verified details.",
    "Agent reviewed the customer's request and provided standard support.",
    "Customer needed help understanding a recent transaction.",
    "Agent followed the normal process and completed the call.",
]
NEGATIVE_TRANSCRIPTS = [
    "Customer was angry about a problem and asked for a supervisor.",
    "Customer said the issue was unacceptable and wanted to cancel.",
    "Customer was frustrated because the problem had not been fixed.",
    "Customer complained about a delay and sounded upset.",
]
NEGATIVE_KEYWORDS = [
    "angry",
    "problem",
    "supervisor",
    "unacceptable",
    "cancel",
    "frustrated",
    "complained",
    "upset",
]

TABLE_FILENAMES = {
    "agents": "agents.csv",
    "timeoff": "timeoff.csv",
    "calls": "calls.csv",
    "transcripts": "transcripts.csv",
    "daily_labels": "daily_labels.csv",
}

EXPECTED_COLUMNS = {
    "agents": {
        "agent_id",
        "name",
        "team",
        "role",
        "start_date",
        "baseline_calls_per_day",
        "baseline_avg_acw",
        "baseline_avg_call_duration",
    },
    "timeoff": {
        "timeoff_id",
        "agent_id",
        "pto_balance_hours",
        "vacation_days_available",
        "pto_used_hours_30d",
        "last_pto_date",
    },
    "calls": {
        "call_id",
        "agent_id",
        "call_date",
        "duration_seconds",
        "acw_seconds",
        "hold_seconds",
        "transfer_count",
        "transcript_id",
    },
    "transcripts": {
        "transcript_id",
        "call_id",
        "transcript_text",
        "sentiment_label",
        "sentiment_score",
        "negative_keyword_count",
    },
    "daily_labels": {
        "agent_id",
        "label_date",
        "latent_pressure_score",
        "pressure_band",
        "simulated_pressure_event",
        "synthetic_stress_label",
    },
}


class DataValidationError(ValueError):
    """Raised when generated tables are incomplete or internally inconsistent."""


@dataclass(frozen=True)
class GenerationConfig:
    """All inputs needed to reproduce a synthetic-data run."""

    num_agents: int = 50
    start_date: date = date(2026, 1, 1)
    num_days: int = 30
    seed: int = 42
    output_dir: Path = Path("data/synthetic")
    at_risk_fraction: float = 0.20
    pressure_event_probability: float = 0.12

    def __post_init__(self) -> None:
        if self.num_agents < 1:
            raise ValueError("num_agents must be at least 1")
        if self.num_days < 1:
            raise ValueError("num_days must be at least 1")
        if not 0 <= self.at_risk_fraction <= 1:
            raise ValueError("at_risk_fraction must be between 0 and 1")
        if not 0 <= self.pressure_event_probability <= 1:
            raise ValueError("pressure_event_probability must be between 0 and 1")

    @property
    def end_date(self) -> date:
        """Return the last simulated date, inclusive."""
        return self.start_date + timedelta(days=self.num_days - 1)

    def to_manifest_dict(self) -> dict[str, object]:
        """Return JSON-safe settings for the generation manifest."""
        return {
            "num_agents": self.num_agents,
            "start_date": self.start_date.isoformat(),
            "num_days": self.num_days,
            "seed": self.seed,
            "output_dir": str(self.output_dir),
            "at_risk_fraction": self.at_risk_fraction,
            "pressure_event_probability": self.pressure_event_probability,
        }


def _default_rng() -> np.random.Generator:
    """Provide deterministic behavior for direct function calls in tutorials/tests."""
    return np.random.default_rng(42)


def _seeded_faker(seed: int) -> Faker:
    faker = Faker()
    faker.seed_instance(seed)
    return faker


def generate_agents(
    num_agents: int = 50,
    *,
    rng: np.random.Generator | None = None,
    faker: Faker | None = None,
    reference_date: date = date(2026, 1, 1),
) -> pd.DataFrame:
    """Generate agents and a personal normal-work baseline for each one."""
    if num_agents < 1:
        raise ValueError("num_agents must be at least 1")

    rng = rng or _default_rng()
    faker = faker or _seeded_faker(42)
    agents: list[dict[str, object]] = []

    for agent_id in range(1, num_agents + 1):
        employment_days = int(rng.integers(30, 5 * 365 + 1))
        agents.append(
            {
                "agent_id": agent_id,
                "name": faker.name(),
                "team": str(rng.choice(TEAMS)),
                "role": str(rng.choice(ROLES)),
                "start_date": reference_date - timedelta(days=employment_days),
                "baseline_calls_per_day": int(rng.integers(25, 55)),
                "baseline_avg_acw": int(rng.integers(90, 240)),
                "baseline_avg_call_duration": int(rng.integers(300, 750)),
            }
        )

    return pd.DataFrame(agents)


def generate_timeoff(
    agents_df: pd.DataFrame,
    *,
    rng: np.random.Generator | None = None,
    reference_date: date = date(2026, 1, 30),
) -> pd.DataFrame:
    """Generate one recovery/time-off snapshot per agent."""
    rng = rng or _default_rng()
    timeoff_records: list[dict[str, object]] = []

    for timeoff_id, agent_id in enumerate(agents_df["agent_id"], start=1):
        days_since_pto = int(rng.integers(0, 181))
        timeoff_records.append(
            {
                "timeoff_id": timeoff_id,
                "agent_id": int(agent_id),
                "pto_balance_hours": int(rng.integers(0, 120)),
                "vacation_days_available": int(rng.integers(0, 15)),
                "pto_used_hours_30d": int(rng.integers(0, 32)),
                "last_pto_date": reference_date - timedelta(days=days_since_pto),
            }
        )

    return pd.DataFrame(timeoff_records)


def generate_daily_labels(
    agents_df: pd.DataFrame,
    *,
    start_date: date,
    num_days: int,
    rng: np.random.Generator | None = None,
    at_risk_fraction: float = 0.20,
    pressure_event_probability: float = 0.12,
) -> pd.DataFrame:
    """Create hidden synthetic pressure trajectories and explicit research labels.

    These labels exist only to exercise the later machine-learning pipeline. They
    are simulated ground truth, not observed or clinically validated burnout.
    """
    if num_days < 1:
        raise ValueError("num_days must be at least 1")
    if not 0 <= at_risk_fraction <= 1:
        raise ValueError("at_risk_fraction must be between 0 and 1")
    if not 0 <= pressure_event_probability <= 1:
        raise ValueError("pressure_event_probability must be between 0 and 1")

    rng = rng or _default_rng()
    agent_ids = agents_df["agent_id"].astype(int).to_numpy()
    at_risk_count = int(round(len(agent_ids) * at_risk_fraction))
    at_risk_ids: set[int] = set()
    if at_risk_count:
        selected = rng.choice(agent_ids, size=at_risk_count, replace=False)
        at_risk_ids = {int(agent_id) for agent_id in np.atleast_1d(selected)}

    records: list[dict[str, object]] = []
    denominator = max(num_days - 1, 1)

    for agent_id in agent_ids:
        is_at_risk = int(agent_id) in at_risk_ids
        base_pressure = float(rng.uniform(0.18, 0.38))
        trend_ceiling = float(rng.uniform(0.24, 0.44)) if is_at_risk else 0.0
        carried_pressure = base_pressure

        for day_index in range(num_days):
            label_date = start_date + timedelta(days=day_index)
            pressure_event = bool(rng.random() < pressure_event_probability)
            event_boost = float(rng.uniform(0.18, 0.34)) if pressure_event else 0.0
            trend = trend_ceiling * (day_index / denominator)
            weekend_recovery = 0.08 if label_date.weekday() >= 5 else 0.0
            raw_pressure = (
                base_pressure
                + trend
                + event_boost
                - weekend_recovery
                + float(rng.normal(0, 0.05))
            )
            smoothed_pressure = float(
                np.clip(0.55 * carried_pressure + 0.45 * raw_pressure, 0.0, 1.0)
            )
            carried_pressure = smoothed_pressure

            if smoothed_pressure >= 0.65:
                pressure_band = "High"
            elif smoothed_pressure >= 0.40:
                pressure_band = "Elevated"
            else:
                pressure_band = "Low"

            records.append(
                {
                    "agent_id": int(agent_id),
                    "label_date": label_date,
                    "latent_pressure_score": round(smoothed_pressure, 4),
                    "pressure_band": pressure_band,
                    "simulated_pressure_event": pressure_event,
                    "synthetic_stress_label": int(smoothed_pressure >= 0.65),
                }
            )

    return pd.DataFrame(records)


def choose_transcript_and_sentiment(
    difficulty: float,
    *,
    rng: np.random.Generator | None = None,
) -> tuple[str, str, float, int]:
    """Choose synthetic call text and sentiment for a call difficulty value."""
    if not 0 <= difficulty <= 1:
        raise ValueError("difficulty must be between 0 and 1")

    rng = rng or _default_rng()
    if difficulty >= 0.75:
        transcript_text = str(rng.choice(NEGATIVE_TRANSCRIPTS))
        sentiment_label = "Negative"
        sentiment_score = round(float(rng.uniform(-1.0, -0.35)), 2)
    elif difficulty >= 0.45:
        transcript_text = str(rng.choice(NEUTRAL_TRANSCRIPTS))
        sentiment_label = "Neutral"
        sentiment_score = round(float(rng.uniform(-0.25, 0.25)), 2)
    else:
        transcript_text = str(rng.choice(POSITIVE_TRANSCRIPTS))
        sentiment_label = "Positive"
        sentiment_score = round(float(rng.uniform(0.35, 1.0)), 2)

    negative_keyword_count = sum(
        1 for word in NEGATIVE_KEYWORDS if word in transcript_text.lower()
    )
    return transcript_text, sentiment_label, sentiment_score, negative_keyword_count


def generate_calls_and_transcripts(
    agents_df: pd.DataFrame,
    start_date: str | date = "2026-01-01",
    num_days: int = 30,
    *,
    daily_labels_df: pd.DataFrame | None = None,
    rng: np.random.Generator | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate related call and transcript rows influenced by daily pressure."""
    if num_days < 1:
        raise ValueError("num_days must be at least 1")
    if isinstance(start_date, str):
        first_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        first_date = start_date

    rng = rng or _default_rng()
    pressure_lookup: dict[tuple[int, date], float] = {}
    if daily_labels_df is not None:
        pressure_lookup = {
            (int(row.agent_id), pd.Timestamp(row.label_date).date()): float(
                row.latent_pressure_score
            )
            for row in daily_labels_df.itertuples(index=False)
        }

    calls: list[dict[str, object]] = []
    transcripts: list[dict[str, object]] = []
    call_id = 1
    transcript_id = 1

    for agent in agents_df.itertuples(index=False):
        agent_id = int(agent.agent_id)
        baseline_calls = int(agent.baseline_calls_per_day)
        baseline_duration = int(agent.baseline_avg_call_duration)
        baseline_acw = int(agent.baseline_avg_acw)

        for day_index in range(num_days):
            call_date = first_date + timedelta(days=day_index)
            daily_pressure = pressure_lookup.get(
                (agent_id, call_date),
                float(rng.uniform(0.18, 0.58)),
            )
            weekend_multiplier = 0.60 if call_date.weekday() >= 5 else 1.0
            pressure_multiplier = 0.82 + 0.55 * daily_pressure
            calls_today = max(
                1,
                int(
                    rng.normal(
                        baseline_calls * weekend_multiplier * pressure_multiplier,
                        4,
                    )
                ),
            )

            for _ in range(calls_today):
                difficulty = float(
                    np.clip(rng.beta(2.0 + 4.0 * daily_pressure, 4.5), 0.0, 1.0)
                )
                duration_seconds = max(
                    120,
                    int(rng.normal(baseline_duration * (1 + difficulty * 0.40), 90)),
                )
                acw_seconds = max(
                    30,
                    int(rng.normal(baseline_acw * (1 + difficulty * 0.50), 45)),
                )
                hold_seconds = max(
                    0,
                    int(rng.normal(45 * (1 + difficulty * 2), 30)),
                )
                transfer_count = int(rng.choice([0, 1, 2, 3], p=[0.72, 0.20, 0.06, 0.02]))
                transcript = choose_transcript_and_sentiment(difficulty, rng=rng)
                transcript_text, sentiment_label, sentiment_score, keyword_count = transcript

                calls.append(
                    {
                        "call_id": call_id,
                        "agent_id": agent_id,
                        "call_date": call_date,
                        "duration_seconds": duration_seconds,
                        "acw_seconds": acw_seconds,
                        "hold_seconds": hold_seconds,
                        "transfer_count": transfer_count,
                        "transcript_id": transcript_id,
                    }
                )
                transcripts.append(
                    {
                        "transcript_id": transcript_id,
                        "call_id": call_id,
                        "transcript_text": transcript_text,
                        "sentiment_label": sentiment_label,
                        "sentiment_score": sentiment_score,
                        "negative_keyword_count": keyword_count,
                    }
                )
                call_id += 1
                transcript_id += 1

    return pd.DataFrame(calls), pd.DataFrame(transcripts)


def generate_dataset(config: GenerationConfig) -> dict[str, pd.DataFrame]:
    """Generate every table from one configuration and validate the result."""
    rng = np.random.default_rng(config.seed)
    faker = _seeded_faker(config.seed)
    agents = generate_agents(
        config.num_agents,
        rng=rng,
        faker=faker,
        reference_date=config.start_date,
    )
    timeoff = generate_timeoff(agents, rng=rng, reference_date=config.end_date)
    daily_labels = generate_daily_labels(
        agents,
        start_date=config.start_date,
        num_days=config.num_days,
        rng=rng,
        at_risk_fraction=config.at_risk_fraction,
        pressure_event_probability=config.pressure_event_probability,
    )
    calls, transcripts = generate_calls_and_transcripts(
        agents,
        start_date=config.start_date,
        num_days=config.num_days,
        daily_labels_df=daily_labels,
        rng=rng,
    )
    tables = {
        "agents": agents,
        "timeoff": timeoff,
        "calls": calls,
        "transcripts": transcripts,
        "daily_labels": daily_labels,
    }
    validate_generated_data(tables)
    return tables


def collect_validation_errors(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Return every detectable schema, range, and relationship problem."""
    errors: list[str] = []
    missing_tables = sorted(set(EXPECTED_COLUMNS) - set(tables))
    if missing_tables:
        return [f"Missing tables: {', '.join(missing_tables)}"]

    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        table = tables[table_name]
        missing_columns = sorted(expected_columns - set(table.columns))
        if missing_columns:
            errors.append(f"{table_name} is missing columns: {', '.join(missing_columns)}")
        if table.empty:
            errors.append(f"{table_name} must not be empty")
        if table.isna().any().any():
            errors.append(f"{table_name} contains missing values")

    if errors:
        return errors

    agents = tables["agents"]
    timeoff = tables["timeoff"]
    calls = tables["calls"]
    transcripts = tables["transcripts"]
    daily_labels = tables["daily_labels"]
    agent_ids = set(agents["agent_id"].astype(int))

    unique_checks = [
        ("agents.agent_id", agents["agent_id"]),
        ("timeoff.timeoff_id", timeoff["timeoff_id"]),
        ("timeoff.agent_id", timeoff["agent_id"]),
        ("calls.call_id", calls["call_id"]),
        ("calls.transcript_id", calls["transcript_id"]),
        ("transcripts.call_id", transcripts["call_id"]),
        ("transcripts.transcript_id", transcripts["transcript_id"]),
    ]
    for field_name, values in unique_checks:
        if not values.is_unique:
            errors.append(f"{field_name} contains duplicate values")

    if set(timeoff["agent_id"].astype(int)) != agent_ids:
        errors.append("timeoff must contain exactly one record for every agent")
    if not set(calls["agent_id"].astype(int)).issubset(agent_ids):
        errors.append("calls contains an agent_id that is missing from agents")
    if not set(daily_labels["agent_id"].astype(int)).issubset(agent_ids):
        errors.append("daily_labels contains an agent_id that is missing from agents")

    linked_calls = set(zip(calls["call_id"], calls["transcript_id"], strict=True))
    linked_transcripts = set(
        zip(transcripts["call_id"], transcripts["transcript_id"], strict=True)
    )
    if linked_calls != linked_transcripts:
        errors.append("calls and transcripts do not have matching call/transcript pairs")

    if daily_labels.duplicated(["agent_id", "label_date"]).any():
        errors.append("daily_labels contains duplicate agent/date pairs")
    unique_dates = daily_labels["label_date"].nunique()
    if len(daily_labels) != len(agent_ids) * unique_dates:
        errors.append("daily_labels must contain one row per agent per simulated date")

    range_checks = [
        ("agents.baseline_calls_per_day", agents["baseline_calls_per_day"].ge(1)),
        ("agents.baseline_avg_acw", agents["baseline_avg_acw"].ge(0)),
        ("agents.baseline_avg_call_duration", agents["baseline_avg_call_duration"].ge(1)),
        ("timeoff.pto_balance_hours", timeoff["pto_balance_hours"].ge(0)),
        ("timeoff.vacation_days_available", timeoff["vacation_days_available"].ge(0)),
        ("timeoff.pto_used_hours_30d", timeoff["pto_used_hours_30d"].ge(0)),
        ("calls.duration_seconds", calls["duration_seconds"].ge(120)),
        ("calls.acw_seconds", calls["acw_seconds"].ge(30)),
        ("calls.hold_seconds", calls["hold_seconds"].ge(0)),
        ("transcripts.sentiment_score", transcripts["sentiment_score"].between(-1, 1)),
        ("transcripts.negative_keyword_count", transcripts["negative_keyword_count"].ge(0)),
        (
            "daily_labels.latent_pressure_score",
            daily_labels["latent_pressure_score"].between(0, 1),
        ),
    ]
    for field_name, valid_rows in range_checks:
        if not bool(valid_rows.all()):
            errors.append(f"{field_name} contains values outside its allowed range")

    if not calls["transfer_count"].isin([0, 1, 2, 3]).all():
        errors.append("calls.transfer_count contains an unsupported value")
    if not transcripts["sentiment_label"].isin(["Positive", "Neutral", "Negative"]).all():
        errors.append("transcripts.sentiment_label contains an unsupported value")
    if not daily_labels["pressure_band"].isin(["Low", "Elevated", "High"]).all():
        errors.append("daily_labels.pressure_band contains an unsupported value")
    if not daily_labels["synthetic_stress_label"].isin([0, 1]).all():
        errors.append("daily_labels.synthetic_stress_label must contain only 0 or 1")

    date_fields = [
        ("agents.start_date", agents["start_date"]),
        ("timeoff.last_pto_date", timeoff["last_pto_date"]),
        ("calls.call_date", calls["call_date"]),
        ("daily_labels.label_date", daily_labels["label_date"]),
    ]
    for field_name, values in date_fields:
        if pd.to_datetime(values, errors="coerce").isna().any():
            errors.append(f"{field_name} contains an invalid date")

    return errors


def validate_generated_data(tables: dict[str, pd.DataFrame]) -> None:
    """Raise one readable exception containing all validation errors."""
    errors = collect_validation_errors(tables)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise DataValidationError(f"Generated data validation failed:\n{details}")


def write_dataset(tables: dict[str, pd.DataFrame], config: GenerationConfig) -> Path:
    """Write validated tables and a deterministic manifest to the configured folder."""
    validate_generated_data(tables)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    for table_name, filename in TABLE_FILENAMES.items():
        tables[table_name].to_csv(config.output_dir / filename, index=False)

    manifest = {
        "schema_version": 1,
        "synthetic_only": True,
        "configuration": config.to_manifest_dict(),
        "row_counts": {name: len(table) for name, table in tables.items()},
        "files": TABLE_FILENAMES,
    }
    manifest_path = config.output_dir / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest_path


def generate_and_write(config: GenerationConfig) -> dict[str, pd.DataFrame]:
    """Run the complete generation, validation, and write pipeline."""
    tables = generate_dataset(config)
    write_dataset(tables, config)
    return tables


def parse_iso_date(value: str) -> date:
    """Convert a YYYY-MM-DD command-line value into a date."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from error


def build_parser() -> argparse.ArgumentParser:
    """Build the beginner-friendly command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-agents", type=int, default=50)
    parser.add_argument("--start-date", type=parse_iso_date, default=date(2026, 1, 1))
    parser.add_argument("--num-days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--at-risk-fraction", type=float, default=0.20)
    parser.add_argument("--pressure-event-probability", type=float, default=0.12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the configurable pipeline from a terminal command."""
    args = build_parser().parse_args(argv)
    config = GenerationConfig(
        num_agents=args.num_agents,
        start_date=args.start_date,
        num_days=args.num_days,
        seed=args.seed,
        output_dir=args.output_dir,
        at_risk_fraction=args.at_risk_fraction,
        pressure_event_probability=args.pressure_event_probability,
    )
    tables = generate_and_write(config)

    print("Synthetic Affectra data created and validated.")
    print(f"Configuration: {config.to_manifest_dict()}")
    for table_name, table in tables.items():
        print(f"{table_name}: {len(table):,} rows")
    print(f"Files saved to: {config.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
