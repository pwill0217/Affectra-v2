import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)


OUTPUT_DIR = Path("data/synthetic")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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


def generate_agents(num_agents: int = 50) -> pd.DataFrame:
    """Generate fake agents and a personal workload baseline for each one."""
    agents = []

    for agent_id in range(1, num_agents + 1):
        baseline_calls = np.random.randint(25, 55)
        baseline_acw = np.random.randint(90, 240)
        baseline_duration = np.random.randint(300, 750)

        agents.append(
            {
                "agent_id": agent_id,
                "name": fake.name(),
                "team": random.choice(TEAMS),
                "role": random.choice(ROLES),
                "start_date": fake.date_between(start_date="-5y", end_date="-30d"),
                "baseline_calls_per_day": baseline_calls,
                "baseline_avg_acw": baseline_acw,
                "baseline_avg_call_duration": baseline_duration,
            }
        )

    return pd.DataFrame(agents)


def generate_timeoff(agents_df: pd.DataFrame) -> pd.DataFrame:
    """Generate fake PTO and vacation data for each agent."""
    timeoff_records = []

    for _, agent in agents_df.iterrows():
        timeoff_records.append(
            {
                "timeoff_id": len(timeoff_records) + 1,
                "agent_id": agent["agent_id"],
                "pto_balance_hours": np.random.randint(0, 120),
                "vacation_days_available": np.random.randint(0, 15),
                "pto_used_hours_30d": np.random.randint(0, 32),
                "last_pto_date": fake.date_between(start_date="-180d", end_date="today"),
            }
        )

    return pd.DataFrame(timeoff_records)


def choose_transcript_and_sentiment(stress_factor: float) -> tuple[str, str, float, int]:
    """Pick a synthetic transcript and sentiment values for a call difficulty level."""
    if stress_factor >= 0.75:
        transcript_text = random.choice(NEGATIVE_TRANSCRIPTS)
        sentiment_label = "Negative"
        sentiment_score = round(np.random.uniform(-1.0, -0.35), 2)
    elif stress_factor >= 0.45:
        transcript_text = random.choice(NEUTRAL_TRANSCRIPTS)
        sentiment_label = "Neutral"
        sentiment_score = round(np.random.uniform(-0.25, 0.25), 2)
    else:
        transcript_text = random.choice(POSITIVE_TRANSCRIPTS)
        sentiment_label = "Positive"
        sentiment_score = round(np.random.uniform(0.35, 1.0), 2)

    negative_keywords = [
        "angry",
        "problem",
        "supervisor",
        "unacceptable",
        "cancel",
        "frustrated",
        "complained",
        "upset",
    ]
    negative_keyword_count = sum(
        1 for word in negative_keywords if word in transcript_text.lower()
    )

    return transcript_text, sentiment_label, sentiment_score, negative_keyword_count


def generate_calls_and_transcripts(
    agents_df: pd.DataFrame,
    start_date: str = "2026-01-01",
    num_days: int = 30,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate related call and transcript records for several days."""
    calls = []
    transcripts = []
    first_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    call_id = 1
    transcript_id = 1

    for _, agent in agents_df.iterrows():
        agent_id = agent["agent_id"]
        baseline_calls = int(agent["baseline_calls_per_day"])
        baseline_duration = int(agent["baseline_avg_call_duration"])
        baseline_acw = int(agent["baseline_avg_acw"])

        for day in range(num_days):
            call_date = first_date + timedelta(days=day)
            weekend_multiplier = 0.60 if call_date.weekday() >= 5 else 1.0
            daily_pressure = np.random.uniform(0.75, 1.45)
            calls_today = max(
                1,
                int(np.random.normal(baseline_calls * weekend_multiplier * daily_pressure, 5)),
            )

            for _ in range(calls_today):
                call_difficulty = np.random.uniform(0, 1)
                duration_seconds = max(
                    120,
                    int(
                        np.random.normal(
                            baseline_duration * (1 + call_difficulty * 0.40),
                            90,
                        )
                    ),
                )
                acw_seconds = max(
                    30,
                    int(
                        np.random.normal(
                            baseline_acw * (1 + call_difficulty * 0.50),
                            45,
                        )
                    ),
                )
                hold_seconds = max(
                    0,
                    int(np.random.normal(45 * (1 + call_difficulty * 2), 30)),
                )
                transfer_count = np.random.choice([0, 1, 2, 3], p=[0.72, 0.20, 0.06, 0.02])

                (
                    transcript_text,
                    sentiment_label,
                    sentiment_score,
                    negative_keyword_count,
                ) = choose_transcript_and_sentiment(call_difficulty)

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
                        "negative_keyword_count": negative_keyword_count,
                    }
                )
                call_id += 1
                transcript_id += 1

    return pd.DataFrame(calls), pd.DataFrame(transcripts)


def main() -> None:
    """Generate the default 30-day synthetic dataset and save four CSV files."""
    print("Generating synthetic Affectra data...")

    agents_df = generate_agents(num_agents=50)
    timeoff_df = generate_timeoff(agents_df)
    calls_df, transcripts_df = generate_calls_and_transcripts(
        agents_df=agents_df,
        start_date="2026-01-01",
        num_days=30,
    )

    agents_df.to_csv(OUTPUT_DIR / "agents.csv", index=False)
    timeoff_df.to_csv(OUTPUT_DIR / "timeoff.csv", index=False)
    calls_df.to_csv(OUTPUT_DIR / "calls.csv", index=False)
    transcripts_df.to_csv(OUTPUT_DIR / "transcripts.csv", index=False)

    print("Synthetic data created successfully.")
    print(f"Agents: {len(agents_df)}")
    print(f"Time off records: {len(timeoff_df)}")
    print(f"Calls: {len(calls_df)}")
    print(f"Transcripts: {len(transcripts_df)}")
    print(f"Files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
