from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".matplotlib-cache"))

import matplotlib.pyplot as plt
import pandas as pd

COUNTED_STATUSES = {"completed", "saved_partial"}

plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Noto Sans CJK TC",
    "Arial Unicode MS",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


def normalize_sessions(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "date",
                "start_time",
                "end_time",
                "subject",
                "book_or_course",
                "chapter",
                "task_type",
                "proof_status",
                "plan_note",
                "focus_minutes",
                "break_minutes",
                "completed_pomodoros",
                "pomodoro_minutes",
                "status",
                "output",
                "stuck",
                "next_action",
                "created_at",
                "updated_at",
            ]
        )

    normalized = df.copy()
    for column in ["focus_minutes", "break_minutes", "completed_pomodoros", "pomodoro_minutes"]:
        normalized[column] = pd.to_numeric(_column(normalized, column, 0), errors="coerce").fillna(0)
    normalized["date"] = pd.to_datetime(_column(normalized, "date", ""), errors="coerce").dt.date
    normalized["status"] = _column(normalized, "status", "").astype(str)
    for column in [
        "subject",
        "book_or_course",
        "chapter",
        "task_type",
        "proof_status",
        "plan_note",
        "output",
        "stuck",
        "next_action",
    ]:
        normalized[column] = _column(normalized, column, "").fillna("").astype(str)
    return normalized


def _column(df: pd.DataFrame, column: str, default: Any) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series([default] * len(df), index=df.index)


def counted_sessions(df: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_sessions(df)
    if normalized.empty:
        return normalized
    return normalized[normalized["status"].isin(COUNTED_STATUSES)].copy()


def today_records(df: pd.DataFrame, today: date) -> pd.DataFrame:
    normalized = normalize_sessions(df)
    if normalized.empty:
        return normalized
    return normalized[normalized["date"] == today].copy()


def today_summary(df: pd.DataFrame, today: date) -> dict[str, Any]:
    records = today_records(df, today)
    counted = counted_sessions(records)
    subject_hours = _hours_by(counted, "subject")
    focus_minutes = float(counted["focus_minutes"].sum()) if not counted.empty else 0.0
    pomodoros = int(counted["completed_pomodoros"].sum()) if not counted.empty else 0
    return {
        "records": records,
        "focus_minutes": round(focus_minutes, 2),
        "study_hours": round(focus_minutes / 60, 2),
        "pomodoros": pomodoros,
        "subject_hours": subject_hours,
    }


def cumulative_summary(df: pd.DataFrame, today: date) -> dict[str, Any]:
    counted = counted_sessions(df)
    total_minutes = float(counted["focus_minutes"].sum()) if not counted.empty else 0.0
    total_pomodoros = int(counted["completed_pomodoros"].sum()) if not counted.empty else 0
    daily = daily_hours(counted)
    weekly = weekly_hours(counted)
    return {
        "counted": counted,
        "total_hours": round(total_minutes / 60, 2),
        "total_pomodoros": total_pomodoros,
        "subject_hours": _hours_by(counted, "subject"),
        "task_type_hours": _hours_by(counted, "task_type"),
        "daily_hours": daily,
        "weekly_hours": weekly,
        "average_7_days": average_hours(counted, today, 7),
        "average_30_days": average_hours(counted, today, 30),
    }


def _hours_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[column, "hours"])
    result = (
        df.groupby(column, dropna=False)["focus_minutes"]
        .sum()
        .reset_index()
        .rename(columns={"focus_minutes": "minutes"})
    )
    result["hours"] = (result["minutes"] / 60).round(2)
    result = result.drop(columns=["minutes"])
    result[column] = result[column].replace("", "(未填)")
    return result.sort_values("hours", ascending=False).reset_index(drop=True)


def daily_hours(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "hours"])
    result = df.dropna(subset=["date"]).groupby("date")["focus_minutes"].sum().reset_index()
    result["hours"] = (result["focus_minutes"] / 60).round(2)
    return result.drop(columns=["focus_minutes"]).sort_values("date").reset_index(drop=True)


def daily_hours_between(df: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    all_dates = pd.date_range(start=start_date, end=end_date, freq="D")
    base = pd.DataFrame({"date": all_dates.date})
    counted = counted_sessions(df)
    if counted.empty:
        base["hours"] = 0.0
        return base

    window = counted[(counted["date"] >= start_date) & (counted["date"] <= end_date)]
    if window.empty:
        base["hours"] = 0.0
        return base

    grouped = daily_hours(window)
    result = base.merge(grouped, on="date", how="left")
    result["hours"] = result["hours"].fillna(0.0).round(2)
    return result


def weekly_hours(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["week_start", "week_end", "hours", "pomodoros"])

    working = df.dropna(subset=["date"]).copy()
    if working.empty:
        return pd.DataFrame(columns=["week_start", "week_end", "hours", "pomodoros"])

    working["week_start"] = working["date"].apply(lambda d: d - timedelta(days=d.weekday()))
    grouped = (
        working.groupby("week_start")
        .agg(focus_minutes=("focus_minutes", "sum"), pomodoros=("completed_pomodoros", "sum"))
        .reset_index()
    )
    grouped["week_end"] = grouped["week_start"].apply(lambda d: d + timedelta(days=6))
    grouped["hours"] = (grouped["focus_minutes"] / 60).round(2)
    grouped["pomodoros"] = grouped["pomodoros"].astype(int)
    return grouped[["week_start", "week_end", "hours", "pomodoros"]].sort_values("week_start")


def average_hours(df: pd.DataFrame, today: date, days: int) -> float:
    if days <= 0:
        return 0.0
    counted = counted_sessions(df)
    start = today - timedelta(days=days - 1)
    window = counted[(counted["date"] >= start) & (counted["date"] <= today)]
    total_hours = float(window["focus_minutes"].sum()) / 60 if not window.empty else 0.0
    return round(total_hours / days, 2)


def daily_hours_figure(
    daily_df: pd.DataFrame,
    title: str = "每日讀書時數",
    x_label: str = "日期",
    y_label: str = "時數",
    empty_label: str = "尚無資料",
):
    fig, ax = plt.subplots(figsize=(8, 4))
    if daily_df.empty:
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.text(0.5, 0.5, empty_label, ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        return fig

    plot_df = daily_df.copy()
    plot_df["date"] = pd.to_datetime(plot_df["date"])
    ax.plot(plot_df["date"], plot_df["hours"], marker="o", linewidth=2)
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def daily_hours_bar_figure(
    daily_df: pd.DataFrame,
    title: str = "Daily focus hours",
    x_label: str = "Date",
    y_label: str = "Hours",
    empty_label: str = "No data yet",
):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if daily_df.empty:
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.text(0.5, 0.5, empty_label, ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        return fig

    plot_df = daily_df.copy()
    plot_df["date_label"] = pd.to_datetime(plot_df["date"]).dt.strftime("%m-%d")
    bars = ax.bar(plot_df["date_label"], plot_df["hours"], color="#0ea5e9")
    ax.bar_label(bars, fmt="%.2g", padding=3)
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def search_sessions(df: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    result = normalize_sessions(df)
    if result.empty:
        return result

    for column, keyword in filters.items():
        keyword = (keyword or "").strip()
        if not keyword:
            continue
        result = result[result[column].astype(str).str.contains(keyword, case=False, na=False)]
    return result.reset_index(drop=True)
