from __future__ import annotations

import pandas as pd

import analytics


def csv_bytes(df: pd.DataFrame) -> bytes:
    if df is None:
        df = pd.DataFrame()
    return df.to_csv(index=False).encode("utf-8-sig")


def all_records_csv(df: pd.DataFrame) -> bytes:
    return csv_bytes(analytics.normalize_sessions(df))


def today_records_csv(df: pd.DataFrame, today) -> bytes:
    return csv_bytes(analytics.today_records(df, today))


def weekly_summary_csv(df: pd.DataFrame) -> bytes:
    return csv_bytes(analytics.weekly_hours(analytics.counted_sessions(df)))


def subject_stats_csv(df: pd.DataFrame) -> bytes:
    return csv_bytes(analytics.cumulative_summary(df, pd.Timestamp.today().date())["subject_hours"])
