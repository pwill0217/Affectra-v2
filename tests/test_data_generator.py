from datetime import date

import pandas as pd

from src.data_generator import (
    choose_transcript_and_sentiment,
    generate_agents,
    generate_calls_and_transcripts,
    generate_timeoff,
)


def test_generate_agents_has_required_columns_and_unique_ids() -> None:
    agents = generate_agents(num_agents=5)

    expected_columns = {
        "agent_id",
        "name",
        "team",
        "role",
        "start_date",
        "baseline_calls_per_day",
        "baseline_avg_acw",
        "baseline_avg_call_duration",
    }

    assert len(agents) == 5
    assert expected_columns == set(agents.columns)
    assert agents["agent_id"].is_unique
    assert agents["agent_id"].tolist() == [1, 2, 3, 4, 5]
    assert agents["start_date"].map(lambda value: isinstance(value, date)).all()
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


def test_calls_and_transcripts_keep_one_to_one_relationships() -> None:
    agents = generate_agents(num_agents=3)
    calls, transcripts = generate_calls_and_transcripts(
        agents,
        start_date="2026-01-01",
        num_days=2,
    )

    assert not calls.empty
    assert len(calls) == len(transcripts)
    assert calls["call_id"].is_unique
    assert calls["transcript_id"].is_unique
    assert transcripts["call_id"].is_unique
    assert transcripts["transcript_id"].is_unique
    assert set(calls["agent_id"]).issubset(set(agents["agent_id"]))
    assert set(calls["call_id"]) == set(transcripts["call_id"])
    assert set(calls["transcript_id"]) == set(transcripts["transcript_id"])
    assert calls["duration_seconds"].ge(120).all()
    assert calls["acw_seconds"].ge(30).all()
    assert calls["hold_seconds"].ge(0).all()
    assert calls["transfer_count"].isin([0, 1, 2, 3]).all()
    assert transcripts["sentiment_label"].isin(["Positive", "Neutral", "Negative"]).all()
    assert transcripts["sentiment_score"].between(-1, 1).all()

    linked = calls[["call_id", "transcript_id"]].merge(
        transcripts[["call_id", "transcript_id"]],
        on=["call_id", "transcript_id"],
        how="outer",
        indicator=True,
    )
    assert (linked["_merge"] == "both").all()


def test_sentiment_bands_match_difficulty() -> None:
    cases = [
        (0.10, "Positive", (0.35, 1.0)),
        (0.60, "Neutral", (-0.25, 0.25)),
        (0.90, "Negative", (-1.0, -0.35)),
    ]

    for difficulty, expected_label, score_range in cases:
        text, label, score, keyword_count = choose_transcript_and_sentiment(difficulty)

        assert isinstance(text, str) and text
        assert label == expected_label
        assert score_range[0] <= score <= score_range[1]
        assert isinstance(keyword_count, int) and keyword_count >= 0


def test_generator_returns_dataframes() -> None:
    agents = generate_agents(num_agents=1)
    calls, transcripts = generate_calls_and_transcripts(agents, num_days=1)

    assert isinstance(agents, pd.DataFrame)
    assert isinstance(calls, pd.DataFrame)
    assert isinstance(transcripts, pd.DataFrame)
