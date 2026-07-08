from __future__ import annotations

import json
import base64
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

import analytics
import export
import timer_state
from auth import require_passcode
from config import ConfigError, load_config, validate_runtime_config
from sheets_db import SheetsDB

ALARM_PATH = Path(__file__).with_name("Alarm.mp3")
SHORT_ALARM_DURATION_MS = 5000
TIMER_REFRESH_MS = 500
WRITE_AFTER_FINISH_REFRESH_MS = 600


LANGUAGES = {
    "zh": "中文",
    "en": "English",
}

PAGE_KEYS = ["start", "today", "stats", "search", "export"]

LEGACY_PAGE_KEYS = {
    "開始讀書": "start",
    "今日紀錄": "today",
    "累積統計": "stats",
    "搜尋": "search",
    "匯出": "export",
    "Start Studying": "start",
    "Today": "today",
    "Stats": "stats",
    "Search": "search",
    "Export": "export",
}

TASK_TYPES = [
    "reading",
    "note_taking",
    "practice",
    "review",
    "mock_test",
    "correction",
    "course",
    "other",
]

SCHEDULE_MODES = ["manual", "auto"]
SESSION_STATUS_OPTIONS = ["completed", "saved_partial", "stopped"]

SEARCH_FIELDS = [
    "subject",
    "book_or_course",
    "chapter",
    "task_type",
    "output",
    "stuck",
    "next_action",
]

HIDDEN_DISPLAY_COLUMNS = {"id", "created_at", "updated_at"}

UI_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&family=Noto+Sans+TC:wght@400;600;700&display=swap');

:root {
  --bg-1: #f3f7ff;
  --bg-2: #ecfdf5;
  --surface: #ffffff;
  --text: #0f172a;
  --muted: #475569;
  --line: #d4e2fa;
  --ring: #e2e8f0;
  --focus: #0ea5e9;
  --focus-soft: #ecfeff;
  --break: #3b82f6;
  --break-soft: #eff6ff;
  --pause: #f59e0b;
  --pause-soft: #fef3c7;
}

.main .block-container {
  background: linear-gradient(160deg, var(--bg-1), var(--bg-2));
}

html, body, [class*="css"] {
  font-family: "Manrope", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
}

#MainMenu,
[data-testid="stDeployButton"],
[data-testid="stDecoration"],
footer {
    display: none !important;
    visibility: hidden !important;
}

.pom-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 1.2rem;
  margin-bottom: 1rem;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.phase-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border-radius: 999px;
  padding: 0.4rem 0.75rem;
  font-weight: 700;
  border: 1px solid;
  font-size: 0.95rem;
}

.phase-focus {
  color: #0369a1;
  background: var(--focus-soft);
  border-color: #bae6fd;
}

.phase-break {
  color: #1d4ed8;
  background: var(--break-soft);
  border-color: #bfdbfe;
}

.phase-paused {
  color: #b45309;
  background: var(--pause-soft);
  border-color: #fde68a;
}

.phase-completed,
.phase-saved_partial,
.phase-stopped {
  color: #16a34a;
  background: #dcfce7;
  border-color: #bbf7d0;
}

.phase-idle {
  color: #64748b;
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.metric-card {
  border: 1px solid var(--ring);
  border-radius: 14px;
  background: #fbfdff;
  padding: 0.8rem;
}

.metric-label {
  color: var(--muted);
  font-size: 0.84rem;
  margin-bottom: 0.35rem;
}

.metric-value {
  color: var(--text);
  font-weight: 700;
  font-size: 1.45rem;
  line-height: 1.2;
}

.subtle-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.75rem 1rem;
  background: #ffffff;
  margin: 0.5rem 0 1rem;
}

.stButton > button {
  border-radius: 12px !important;
  border: 1px solid #bfdbfe !important;
  background: linear-gradient(90deg, #e0f2fe, #dbeafe) !important;
  color: #0f172a !important;
  font-weight: 700;
  transition: all .2s ease !important;
}

.stButton > button:hover {
  transform: translateY(-1px);
  border-color: #93c5fd !important;
}
</style>
"""

I18N = {
    "zh": {
        "app_title": "讀書番茄鐘紀錄系統",
        "language": "語言",
        "page": "頁面",
        "page_start": "開始讀書",
        "page_today": "今日紀錄",
        "page_stats": "累積統計",
        "page_search": "搜尋",
        "page_export": "匯出",
        "google_error": "Google Sheets 連線失敗。請確認 Sheet ID、service account secrets，以及 Sheet 分享權限。",
        "write_events_error": "寫入 pomodoro_events 失敗",
        "write_sessions_error": "寫入 study_sessions 失敗",
        "syncing": "紀錄已完成，正在同步到 Google Sheets。",
        "synced": "紀錄已同步到 Google Sheets。",
        "timer_title": "目前計時",
        "status": "狀態",
        "remaining_time": "剩餘時間",
        "hide_time": "隱藏",
        "show_time": "顯示",
        "focused_time": "已專注時間",
        "pomodoros": "番茄鐘",
        "break_time": "休息時間",
        "last_status": "上次狀態",
        "idle": "未開始",
        "focus": "專注中",
        "break": "休息中",
        "paused": "已暫停",
        "completed": "已完成",
        "saved_partial": "已儲存部分紀錄",
        "stopped": "已停止",
        "pause": "暫停",
        "resume": "繼續",
        "stop": "停止工作",
        "save_partial": "儲存部分紀錄",
        "start_title": "開始讀書",
        "subject": "科目",
        "book_or_course": "書本或課程",
        "chapter": "章節",
        "task_type": "任務類型",
        "proof_status": "證明掌握程度",
        "pomodoro_minutes": "番茄鐘長度（分鐘）",
        "break_minutes": "休息長度（分鐘）",
        "target_pomodoros": "目標番茄鐘數",
        "plan_note": "開始前備註",
        "start": "開始",
        "new_session": "開始新工作階段",
        "no_autorefresh": "若倒數畫面沒有自動更新，請安裝 requirements.txt 內的 streamlit-autorefresh。",
        "today_focus_minutes": "今日專注分鐘",
        "today_study_hours": "今日讀書時數",
        "today_pomodoros": "今日番茄鐘數",
        "today_subject_hours": "今日各科時數",
        "today_records": "今日所有紀錄",
        "edit_record": "補填或修改",
        "select_record": "選擇紀錄",
        "output": "今日產出",
        "stuck": "卡住問題",
        "next_action": "下次第一件事",
        "save_changes": "儲存修改",
        "updated": "已更新。",
        "total_hours": "總累積時數",
        "total_pomodoros": "總番茄鐘數",
        "avg_7": "最近 7 日平均時數",
        "avg_30": "最近 30 日平均時數",
        "subject_hours": "各科累積時數",
        "task_type_hours": "各任務類型累積時數",
        "daily_line": "每日讀書時數折線圖",
        "weekly_table": "每週讀書時數表",
        "chart_title": "每日讀書時數",
        "chart_x": "日期",
        "chart_y": "時數",
        "chart_empty": "尚無資料",
        "search_results": "搜尋結果筆數",
        "all_records_csv": "全部紀錄 CSV",
        "today_records_csv": "今日紀錄 CSV",
        "weekly_summary_csv": "每週摘要 CSV",
        "subject_stats_csv": "各科統計 CSV",
        "task_reading": "閱讀",
        "task_note_taking": "做筆記",
        "task_practice": "練習題",
        "task_review": "複習",
        "task_mock_test": "模擬測驗",
        "task_correction": "訂正",
        "task_course": "課程",
        "task_other": "其他",
        "custom_task_type": "其他任務類型",
        "proof_not_started": "尚未開始",
        "proof_understood": "理解",
        "proof_can_recall": "可回想",
        "proof_can_solve": "可解題",
        "proof_can_explain": "可講解",
        "proof_needs_review": "需要複習",
        "study_plan_setup": "學習計畫設定",
        "task_information": "任務資訊",
        "summary": "摘要",
        "overall_progress": "整體進度",
        "csv_export": "CSV 匯出",
        "filters": "篩選條件",
        "no_records_today": "目前今天尚無紀錄。",
        "controls": "操作控制",
        "session_ready": "會話準備完成，請點擊下方開始。",
    },
    "en": {
        "app_title": "Study Pomodoro Tracker",
        "language": "Language",
        "page": "Page",
        "page_start": "Start Studying",
        "page_today": "Today",
        "page_stats": "Stats",
        "page_search": "Search",
        "page_export": "Export",
        "google_error": "Google Sheets connection failed. Check Sheet ID, service account secrets, and Sheet sharing permissions.",
        "write_events_error": "Failed to write pomodoro_events",
        "write_sessions_error": "Failed to write study_sessions",
        "syncing": "Session completed. Syncing to Google Sheets.",
        "synced": "Session synced to Google Sheets.",
        "timer_title": "Timer",
        "status": "Status",
        "remaining_time": "Remaining time",
        "hide_time": "Hide",
        "show_time": "Show",
        "focused_time": "Focused time",
        "pomodoros": "Pomodoros",
        "break_time": "Break time",
        "last_status": "Last status",
        "idle": "Idle",
        "focus": "Focusing",
        "break": "On break",
        "paused": "Paused",
        "completed": "Completed",
        "saved_partial": "Saved partial",
        "stopped": "Stopped",
        "pause": "Pause",
        "resume": "Resume",
        "stop": "Stop work",
        "save_partial": "Save partial session",
        "start_title": "Start Studying",
        "subject": "Subject",
        "book_or_course": "Book or course",
        "chapter": "Chapter",
        "task_type": "Task type",
        "proof_status": "Proof status",
        "pomodoro_minutes": "Pomodoro minutes",
        "break_minutes": "Break minutes",
        "target_pomodoros": "Target pomodoros",
        "plan_note": "Plan note",
        "start": "Start",
        "new_session": "Start new work session",
        "no_autorefresh": "If the timer does not refresh automatically, install streamlit-autorefresh from requirements.txt.",
        "today_focus_minutes": "Today's focus minutes",
        "today_study_hours": "Today's study hours",
        "today_pomodoros": "Today's pomodoros",
        "today_subject_hours": "Today's subject hours",
        "today_records": "Today's records",
        "edit_record": "Edit record",
        "select_record": "Select record",
        "output": "Output",
        "stuck": "Stuck",
        "next_action": "Next action",
        "save_changes": "Save changes",
        "updated": "Updated.",
        "total_hours": "Total hours",
        "total_pomodoros": "Total pomodoros",
        "avg_7": "7-day average hours",
        "avg_30": "30-day average hours",
        "subject_hours": "Subject hours",
        "task_type_hours": "Task type hours",
        "daily_line": "Daily study hours chart",
        "weekly_table": "Weekly study hours table",
        "chart_title": "Daily study hours",
        "chart_x": "Date",
        "chart_y": "Hours",
        "chart_empty": "No data yet",
        "search_results": "Search results",
        "all_records_csv": "All records CSV",
        "today_records_csv": "Today records CSV",
        "weekly_summary_csv": "Weekly summary CSV",
        "subject_stats_csv": "Subject stats CSV",
        "task_reading": "Reading",
        "task_note_taking": "Note taking",
        "task_practice": "Practice",
        "task_review": "Review",
        "task_mock_test": "Mock test",
        "task_correction": "Correction",
        "task_course": "Course",
        "task_other": "Other",
        "custom_task_type": "Custom task type",
        "proof_not_started": "Not started",
        "proof_understood": "Understood",
        "proof_can_recall": "Can recall",
        "proof_can_solve": "Can solve",
        "proof_can_explain": "Can explain",
        "proof_needs_review": "Needs review",
        "study_plan_setup": "Study plan setup",
        "task_information": "Task information",
        "summary": "Summary",
        "overall_progress": "Overall progress",
        "csv_export": "CSV Export",
        "filters": "Filters",
        "no_records_today": "No records for today yet.",
        "controls": "Controls",
        "session_ready": "Session ready, please start from below.",
    },
}

I18N["zh"].update(
    {
        "total_focus_minutes": "總專注時間（分鐘）",
        "segment_focus_minutes": "每段專注時間（分鐘）",
        "break_minutes": "每段休息時間（分鐘）",
        "planned_segments": "預計專注段數",
        "segmented_break_hint": "系統會在每段專注之間自動加入休息；最後一段可能較短。",
        "schedule_mode": "計時模式",
        "mode_manual": "手動分段",
        "mode_auto": "自動模式",
        "manual_mode_hint": "手動設定總專注時間、每段專注時間與每段休息時間。",
        "auto_mode_hint": "自動模式會用總時間扣掉段間休息，再把剩餘專注時間平均分成 n 段。",
        "total_time_minutes": "總時間（分鐘，含休息）",
        "auto_segments": "分成幾段專注",
        "total_break_minutes": "總休息時間（分鐘）",
        "auto_total_focus": "自動算出總專注時間",
        "auto_segment_focus": "自動算出每段專注時間",
        "auto_break_per_gap": "自動算出每次休息時間",
        "auto_adjusted_break": "總時間不足以放入原本的休息時間，已自動縮短休息。",
        "auto_actual_break": "實際每段休息時間",
    }
)
COLUMN_LABELS = {
    "zh": {
        "id": "ID",
        "date": "日期",
        "start_time": "開始時間",
        "end_time": "結束時間",
        "subject": "科目",
        "book_or_course": "書本或課程",
        "chapter": "章節",
        "task_type": "任務類型",
        "proof_status": "證明掌握程度",
        "plan_note": "開始前備註",
        "focus_minutes": "專注分鐘",
        "break_minutes": "休息分鐘",
        "completed_pomodoros": "完成番茄鐘",
        "pomodoro_minutes": "番茄鐘長度",
        "status": "狀態",
        "output": "今日產出",
        "stuck": "卡住問題",
        "next_action": "下次第一件事",
        "created_at": "建立時間",
        "updated_at": "更新時間",
        "hours": "時數",
        "week_start": "週開始",
        "week_end": "週結束",
        "pomodoros": "番茄鐘",
    },
    "en": {},
}

I18N["zh"].update(
    {
        "total_focus_minutes": "總專注時間（分鐘）",
        "segment_focus_minutes": "每段專注時間（分鐘）",
        "break_minutes": "每段休息時間（分鐘）",
        "planned_segments": "預計專注段數",
        "segmented_break_hint": "系統會在每段專注之間自動加入休息；最後一段可能較短。",
        "schedule_mode": "計時模式",
        "mode_manual": "手動分段",
        "mode_auto": "自動模式",
        "manual_mode_hint": "手動設定總專注時間、每段專注時間與每段休息時間。",
        "auto_mode_hint": "自動模式會用總時間扣掉段間休息，再把剩餘專注時間平均分成 n 段。",
        "total_time_minutes": "總時間（分鐘，含休息）",
        "auto_segments": "分成幾段專注",
        "total_break_minutes": "總休息時間（分鐘）",
        "auto_total_focus": "自動算出總專注時間",
        "auto_segment_focus": "自動算出每段專注時間",
        "auto_break_per_gap": "自動算出每次休息時間",
        "auto_adjusted_break": "總時間不足以放入原本的休息時間，已自動縮短休息。",
        "auto_actual_break": "實際每段休息時間",
    }
)
I18N["en"].update(
    {
        "total_focus_minutes": "Total focus minutes",
        "segment_focus_minutes": "Focus minutes per segment",
        "break_minutes": "Break minutes per segment",
        "planned_segments": "Planned focus segments",
        "segmented_break_hint": "Breaks are inserted between focus segments automatically; the final segment may be shorter.",
        "schedule_mode": "Timer mode",
        "mode_manual": "Manual segments",
        "mode_auto": "Auto mode",
        "manual_mode_hint": "Set total focus time, focus time per segment, and break time per segment manually.",
        "auto_mode_hint": "Auto mode subtracts breaks from total time, then splits the remaining focus time evenly into n segments.",
        "total_time_minutes": "Total minutes, including breaks",
        "auto_segments": "Number of focus segments",
        "total_break_minutes": "Total break minutes",
        "auto_total_focus": "Calculated total focus time",
        "auto_segment_focus": "Calculated focus time per segment",
        "auto_break_per_gap": "Calculated break time per gap",
        "auto_adjusted_break": "Total time is too short for the requested breaks, so breaks were shortened automatically.",
        "auto_actual_break": "Actual break time per segment",
    }
)

I18N["zh"].update(
    {
        "daily_range_chart": "每日專注時間圖表",
        "chart_start_date": "開始日期",
        "chart_end_date": "結束日期",
        "date_range_swapped": "開始日期晚於結束日期，已自動交換日期區間。",
        "range_chart_title": "日期區間內每日累積專注時間",
        "edit_search_record": "修改搜尋結果紀錄",
        "delete_record": "刪除紀錄",
        "delete_record_warning": "刪除後會移除這筆 study_sessions，也會移除對應的 pomodoro_events。",
        "confirm_delete": "我確認要刪除這筆紀錄",
        "confirm_delete_first": "請先勾選確認刪除。",
        "deleted": "紀錄已刪除。",
    }
)
I18N["en"].update(
    {
        "daily_range_chart": "Daily focus time chart",
        "chart_start_date": "Start date",
        "chart_end_date": "End date",
        "date_range_swapped": "Start date is later than end date, so the range was swapped automatically.",
        "range_chart_title": "Daily accumulated focus time in selected range",
        "edit_search_record": "Edit search result record",
        "delete_record": "Delete record",
        "delete_record_warning": "Deleting removes this study_sessions row and its matching pomodoro_events.",
        "confirm_delete": "I confirm deleting this record",
        "confirm_delete_first": "Please check the confirmation box first.",
        "deleted": "Record deleted.",
    }
)


def configure_page() -> None:
    st.set_page_config(page_title="Study Pomodoro Tracker", layout="wide", initial_sidebar_state="expanded")
    st.markdown(UI_STYLE, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_db(sheet_id: str, credentials_json: str) -> SheetsDB:
    return SheetsDB(sheet_id, json.loads(credentials_json))


def local_today(timezone: str):
    return datetime.now(ZoneInfo(timezone)).date()


def get_language() -> str:
    return st.session_state.get("language", "zh")


def text(key: str, language: str | None = None) -> str:
    lang = language or get_language()
    return I18N.get(lang, I18N["zh"]).get(key, I18N["en"].get(key, key))


def column_label(column: str, language: str) -> str:
    return COLUMN_LABELS.get(language, {}).get(column, column)


def scalar_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value)


def scalar_float(value, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def scalar_int(value, default: int = 0) -> int:
    return int(round(scalar_float(value, float(default))))


def scalar_date(value, fallback: date) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return fallback
    return parsed.date()


def daily_hours_between_compat(df: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if hasattr(analytics, "daily_hours_between"):
        return analytics.daily_hours_between(df, start_date, end_date)

    if start_date > end_date:
        start_date, end_date = end_date, start_date
    base = pd.DataFrame({"date": pd.date_range(start=start_date, end=end_date, freq="D").date})
    counted = analytics.counted_sessions(df)
    if counted.empty:
        base["hours"] = 0.0
        return base
    window = counted[(counted["date"] >= start_date) & (counted["date"] <= end_date)]
    if window.empty:
        base["hours"] = 0.0
        return base
    grouped = analytics.daily_hours(window)
    result = base.merge(grouped, on="date", how="left")
    result["hours"] = result["hours"].fillna(0.0).round(2)
    return result


def daily_hours_bar_figure_compat(
    daily_df: pd.DataFrame,
    title: str,
    x_label: str,
    y_label: str,
    empty_label: str,
):
    if hasattr(analytics, "daily_hours_bar_figure"):
        return analytics.daily_hours_bar_figure(
            daily_df,
            title=title,
            x_label=x_label,
            y_label=y_label,
            empty_label=empty_label,
        )

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.8))
    if daily_df.empty:
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.text(0.5, 0.5, empty_label, ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        return fig

    plot_df = daily_df.copy()
    plot_df["date_label"] = pd.to_datetime(plot_df["date"]).dt.strftime("%m-%d")
    bars = ax.bar(plot_df["date_label"], plot_df["hours"], color="#2563eb", width=0.62)
    labels = [f"{value:.2f} h" if value > 0 else "0" for value in plot_df["hours"]]
    ax.bar_label(bars, labels=labels, padding=4, fontsize=9)
    max_hours = float(plot_df["hours"].max()) if not plot_df.empty else 0.0
    ax.set_ylim(0, max(0.25, max_hours * 1.25))
    ax.set_title(title, fontsize=14, fontweight="bold", pad=14)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def phase_class(phase: str) -> str:
    if phase == "focus":
        return "phase-focus"
    if phase == "break":
        return "phase-break"
    if phase == "paused":
        return "phase-paused"
    if phase in {"completed", "saved_partial", "stopped"}:
        return "phase-completed"
    return "phase-idle"


def render_metric_card(label: str, value: str, icon: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(items: list[tuple[str, str, str]]) -> None:
    if not items:
        return
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            render_metric_card(*item)


def option_label(prefix: str, value: str, language: str) -> str:
    key = f"{prefix}_{value}"
    translated = text(key, language)
    return value if translated == key else translated


def record_option_label(records: pd.DataFrame, record_id: str, language: str) -> str:
    matched = records[records["id"].astype(str) == str(record_id)]
    if matched.empty:
        return ""
    row = matched.iloc[0]
    status = text(str(row.get("status", "")), language)
    parts = [
        str(row.get("date", "")),
        str(row.get("start_time", "")),
        str(row.get("subject", "")),
        str(row.get("book_or_course", "")),
        status,
    ]
    return " | ".join(part for part in parts if part and part != "nan")


def page_label(page_key: str, language: str) -> str:
    return text(f"page_{page_key}", language)


def main() -> None:
    configure_page()
    require_passcode()
    config = load_config()
    try:
        validate_runtime_config(config)
    except ConfigError as exc:
        st.error(str(exc))
        st.stop()

    try:
        db = get_db(config.google_sheet_id, config.credentials_json)
    except Exception as exc:
        st.error(text("google_error"))
        st.exception(exc)
        st.stop()

    timer_state.init_timer_state()
    language = render_sidebar()

    st.title(text("app_title", language))
    page = st.session_state.get("page", "start")

    if page == "start":
        render_start_page(db, config.timezone, language)
    elif page == "today":
        render_today_page(db, config.timezone, language)
    elif page == "stats":
        render_stats_page(db, config.timezone, language)
    elif page == "search":
        render_search_page(db, config.timezone, language)
    elif page == "export":
        render_export_page(db, config.timezone, language)


def render_sidebar() -> str:
    current_language = get_language()
    current_page = normalize_page_key(st.session_state.get("page", "start"))
    st.session_state["page"] = current_page
    language = st.sidebar.selectbox(
        text("language", current_language),
        list(LANGUAGES.keys()),
        index=list(LANGUAGES.keys()).index(current_language),
        format_func=lambda key: LANGUAGES[key],
        key="language",
    )
    st.sidebar.radio(
        text("page", language),
        PAGE_KEYS,
        index=PAGE_KEYS.index(current_page),
        format_func=lambda key: page_label(key, language),
        key="page",
    )
    return language


def normalize_page_key(value: str) -> str:
    if value in PAGE_KEYS:
        return value
    return LEGACY_PAGE_KEYS.get(value, "start")


def drain_pending_writes(db: SheetsDB, language: str) -> None:
    wrote_any = False
    for event in timer_state.pending_pomodoro_events():
        try:
            db.append_pomodoro_event(event)
            timer_state.mark_pomodoro_event_saved(event["id"])
            wrote_any = True
        except Exception as exc:
            st.error(f"{text('write_events_error', language)}: {exc}")
            return

    record = timer_state.pending_session_record()
    if record:
        try:
            db.append_study_session(record)
            timer_state.mark_session_record_saved()
            wrote_any = True
        except Exception as exc:
            st.error(f"{text('write_sessions_error', language)}: {exc}")
            return

    if wrote_any:
        st.toast(text("synced", language))


def request_alarm_stop() -> None:
    st.session_state["alarm_stop_requested"] = True


@st.cache_data(show_spinner=False)
def load_alarm_data_uri(path: str, mtime_ns: int) -> str:
    del mtime_ns
    return "data:audio/mpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def get_alarm_data_uri() -> str:
    if not ALARM_PATH.exists():
        return ""
    stat = ALARM_PATH.stat()
    return load_alarm_data_uri(str(ALARM_PATH), stat.st_mtime_ns)


def consume_alarm_events() -> list[dict[str, int | None]]:
    if hasattr(timer_state, "consume_pending_alarms"):
        return timer_state.consume_pending_alarms()

    if hasattr(timer_state, "consume_pending_alarm_count"):
        legacy_count = timer_state.consume_pending_alarm_count()
        return [{"duration_ms": SHORT_ALARM_DURATION_MS} for _ in range(legacy_count)]

    return []


def delete_session_compat(db: SheetsDB, session_id: str) -> None:
    if hasattr(db, "delete_session"):
        db.delete_session(session_id)
        return

    if not session_id:
        return

    study_ws = getattr(db, "study_ws", None)
    events_ws = getattr(db, "events_ws", None)
    if study_ws is None:
        raise RuntimeError("study_sessions worksheet is unavailable")

    study_header = [str(value).strip() for value in study_ws.row_values(1)]
    study_row = find_worksheet_row(study_ws, study_header, "id", session_id)
    if not study_row:
        raise KeyError(f"找不到 session id：{session_id}")

    if events_ws is not None:
        event_header = [str(value).strip() for value in events_ws.row_values(1)]
        for row_number in reversed(find_worksheet_rows(events_ws, event_header, "session_id", session_id)):
            events_ws.delete_rows(row_number)

    study_ws.delete_rows(study_row)


def find_worksheet_row(worksheet, header: list[str], column: str, value: str) -> int | None:
    rows = find_worksheet_rows(worksheet, header, column, value)
    return rows[0] if rows else None


def find_worksheet_rows(worksheet, header: list[str], column: str, value: str) -> list[int]:
    if not value or column not in header:
        return []
    col_number = header.index(column) + 1
    values = worksheet.col_values(col_number)
    return [
        row_number
        for row_number, cell_value in enumerate(values[1:], start=2)
        if str(cell_value) == str(value)
    ]


def render_start_page(db: SheetsDB, timezone: str, language: str) -> None:
    timer_state.advance_timer(timezone)
    render_alarm_player()
    just_finished = timer_state.consume_just_finished()

    if just_finished:
        if st_autorefresh:
            st_autorefresh(interval=WRITE_AFTER_FINISH_REFRESH_MS, limit=1, key="write_after_finish")
    else:
        drain_pending_writes(db, language)

    if timer_state.is_running() and st_autorefresh:
        st_autorefresh(interval=TIMER_REFRESH_MS, key="timer_refresh")

    if timer_state.should_show_timer_panel():
        render_timer_panel(timezone, language)
        action_taken = render_timer_controls(timezone, language)
        if action_taken:
            st.rerun()
        if timer_state.has_pending_writes():
            st.info(text("syncing", language))
        if not timer_state.is_active():
            if st.button(text("new_session", language), use_container_width=True):
                request_alarm_stop()
                timer_state.reset_timer_state()
                st.rerun()
    else:
        render_start_form(timezone, language)

    if timer_state.is_running() and not st_autorefresh:
        st.info(text("no_autorefresh", language))


def render_timer_panel(timezone: str, language: str) -> None:
    timer = timer_state.get_timer()
    snap = timer_state.snapshot(timezone)

    st.markdown(f"<h2>{text('timer_title', language)}</h2>", unsafe_allow_html=True)
    phase = snap.get("phase", "idle")
    render_status_value(phase, language)

    if snap.get("active"):
        with st.container(border=True):
            render_remaining_time(timer_state.format_seconds(snap["remaining_seconds"]), language)
            st.progress(float(snap["progress"]))
            render_metric_cards(
                [
                    (text("focused_time", language), timer_state.format_seconds(snap["focus_seconds"]), "時間"),
                    (
                        text("pomodoros", language),
                        f'{snap["completed_pomodoros"]} / {snap["target_pomodoros"]}',
                        "番茄",
                    ),
                    (text("break_time", language), timer_state.format_seconds(snap.get("break_elapsed_seconds", 0)), "休息"),
                ]
            )
            st.caption(
                f'{snap.get("subject", "")} / {snap.get("book_or_course", "")} / {snap.get("chapter", "")}'
            )
    else:
        with st.container(border=True):
            render_remaining_time("00:00:00", language)
            st.progress(0.0)
            render_metric_cards(
                [
                    (text("focused_time", language), timer_state.format_seconds(snap.get("focus_seconds", 0)), "時間"),
                    (
                        text("pomodoros", language),
                        f'{snap.get("completed_pomodoros", 0)} / {snap.get("target_pomodoros", 0)}',
                        "番茄",
                    ),
                    (text("break_time", language), timer_state.format_seconds(snap.get("break_elapsed_seconds", 0)), "休息"),
                ]
            )
        if timer.get("saved_message"):
            st.success(f"{text('last_status', language)}: {text(timer['saved_message'], language)}")


def render_alarm_player() -> None:
    pending_alarms = consume_alarm_events()
    stop_requested = bool(st.session_state.pop("alarm_stop_requested", False))
    token = int(st.session_state.get("alarm_refresh_token", 0)) + 1
    st.session_state["alarm_refresh_token"] = token

    alarm_src = get_alarm_data_uri()
    if not alarm_src:
        return

    action_lines = []
    if stop_requested:
        action_lines.append("target.__stopPomodoroAlarm && target.__stopPomodoroAlarm();")
    if pending_alarms:
        latest_alarm = pending_alarms[-1]
        duration_ms = latest_alarm.get("duration_ms") or SHORT_ALARM_DURATION_MS
        action_lines.append(
            f"target.__playPomodoroAlarm && target.__playPomodoroAlarm({token}, {json.dumps(duration_ms)});"
        )

    html = """
    <script>
    (() => {
        const alarmSrc = __ALARM_SRC__;

        const getTargetWindow = () => {
            try {
                if (window.parent && window.parent !== window) {
                    void window.parent.document;
                    return window.parent;
                }
            } catch (error) {
            }
            return window;
        };

        const target = getTargetWindow();
        target.__pomodoroAlarmSrc = alarmSrc;

        const normalizedDurationMs = (maxDurationMs) => {
            const durationMs = Number(maxDurationMs);
            return Number.isFinite(durationMs) && durationMs > 0 ? durationMs : null;
        };

        const scheduleAlarmStop = (alarmToken, maxDurationMs) => {
            const durationMs = normalizedDurationMs(maxDurationMs);
            if (!durationMs) {
                return;
            }
            target.__pomodoroAlarmStopTimer = target.setTimeout(() => {
                target.__stopPomodoroAlarm(alarmToken);
            }, durationMs);
        };

        const toArrayBuffer = (dataUri) => {
            const base64Data = dataUri.split(",")[1] || "";
            const binary = target.atob(base64Data);
            const bytes = new Uint8Array(binary.length);
            for (let index = 0; index < binary.length; index += 1) {
                bytes[index] = binary.charCodeAt(index);
            }
            return bytes.buffer;
        };

        const getAudioContext = () => {
            const AudioContextCtor = target.AudioContext || target.webkitAudioContext;
            if (!AudioContextCtor) {
                return null;
            }
            if (!target.__pomodoroAlarmAudioContext) {
                target.__pomodoroAlarmAudioContext = new AudioContextCtor();
            }
            return target.__pomodoroAlarmAudioContext;
        };

        const getAlarmBuffer = () => {
            if (target.__pomodoroAlarmBufferPromise) {
                return target.__pomodoroAlarmBufferPromise;
            }
            const audioContext = getAudioContext();
            if (!audioContext) {
                return Promise.reject(new Error("AudioContext is unavailable"));
            }
            target.__pomodoroAlarmBufferPromise = audioContext.decodeAudioData(toArrayBuffer(alarmSrc).slice(0));
            return target.__pomodoroAlarmBufferPromise;
        };

        target.__stopPomodoroAlarm = (expectedToken) => {
            if (expectedToken && target.__pomodoroAlarmToken && target.__pomodoroAlarmToken !== expectedToken) {
                return;
            }
            if (target.__pomodoroAlarmStopTimer) {
                target.clearTimeout(target.__pomodoroAlarmStopTimer);
                target.__pomodoroAlarmStopTimer = null;
            }
            if (target.__pomodoroAlarmSource) {
                try {
                    target.__pomodoroAlarmSource.stop(0);
                } catch (error) {
                }
                try {
                    target.__pomodoroAlarmSource.disconnect();
                } catch (error) {
                }
                target.__pomodoroAlarmSource = null;
            }
            if (target.__pomodoroAlarmGain) {
                try {
                    target.__pomodoroAlarmGain.disconnect();
                } catch (error) {
                }
                target.__pomodoroAlarmGain = null;
            }
            if (target.__pomodoroAlarmAudio) {
                try {
                    target.__pomodoroAlarmAudio.pause();
                    target.__pomodoroAlarmAudio.currentTime = 0;
                } catch (error) {
                }
                target.__pomodoroAlarmAudio = null;
            }
            target.__pomodoroAlarmToken = null;
        };

        const playWithHtmlAudio = (alarmToken, maxDurationMs) => {
            target.__stopPomodoroAlarm();
            const audio = new target.Audio(alarmSrc);
            audio.volume = 1;
            audio.loop = false;
            target.__pomodoroAlarmToken = alarmToken;
            target.__pomodoroAlarmAudio = audio;
            audio.play().catch((error) => {
                target.__pomodoroAlarmLastError = String(error);
                console.warn("Pomodoro alarm was blocked by the browser.", error);
            });
            scheduleAlarmStop(alarmToken, maxDurationMs);
        };

        target.__playPomodoroAlarm = async (alarmToken, maxDurationMs) => {
            try {
                const audioContext = getAudioContext();
                if (!audioContext) {
                    throw new Error("AudioContext is unavailable");
                }
                if (audioContext.state === "suspended") {
                    await audioContext.resume();
                }
                const buffer = await getAlarmBuffer();
                target.__stopPomodoroAlarm();
                const source = audioContext.createBufferSource();
                const gain = audioContext.createGain();
                source.buffer = buffer;
                gain.gain.value = 1;
                source.connect(gain);
                gain.connect(audioContext.destination);
                target.__pomodoroAlarmToken = alarmToken;
                target.__pomodoroAlarmSource = source;
                target.__pomodoroAlarmGain = gain;
                source.onended = () => {
                    if (target.__pomodoroAlarmToken === alarmToken) {
                        target.__stopPomodoroAlarm(alarmToken);
                    }
                };
                const durationMs = normalizedDurationMs(maxDurationMs);
                if (durationMs) {
                    source.start(0, 0, durationMs / 1000);
                } else {
                    source.start(0, 0);
                }
                scheduleAlarmStop(alarmToken, maxDurationMs);
            } catch (error) {
                target.__pomodoroAlarmLastError = String(error);
                playWithHtmlAudio(alarmToken, maxDurationMs);
            }
        };

        target.__unlockPomodoroAlarm = () => {
            const audioContext = getAudioContext();
            if (!audioContext) {
                return;
            }
            audioContext.resume().then(() => getAlarmBuffer()).catch((error) => {
                target.__pomodoroAlarmLastError = String(error);
            });
            try {
                const silentBuffer = audioContext.createBuffer(1, 1, Math.max(1, audioContext.sampleRate));
                const silentSource = audioContext.createBufferSource();
                const silentGain = audioContext.createGain();
                silentGain.gain.value = 0;
                silentSource.buffer = silentBuffer;
                silentSource.connect(silentGain);
                silentGain.connect(audioContext.destination);
                silentSource.start(0);
            } catch (error) {
            }
        };

        if (!target.__pomodoroAlarmListenersReady && target.document) {
            target.__pomodoroAlarmListenersReady = true;
            ["pointerdown", "click", "keydown", "touchstart"].forEach((eventName) => {
                target.document.addEventListener(
                    eventName,
                    () => target.__unlockPomodoroAlarm && target.__unlockPomodoroAlarm(),
                    { capture: true, passive: true }
                );
            });
        }

        __ALARM_ACTIONS__
    })();
    </script>
    """
    html = html.replace("__ALARM_SRC__", json.dumps(alarm_src))
    html = html.replace("__ALARM_ACTIONS__", "\n        ".join(action_lines))
    components.html(
        html,
        height=1,
    )


def render_remaining_time(value: str, language: str) -> None:
    hidden = st.session_state.get("hide_remaining_time", False)
    metric_col, button_col = st.columns([5, 1])
    metric_col.metric(text("remaining_time", language), "--:--:--" if hidden else value)
    if button_col.button(
        text("show_time" if hidden else "hide_time", language),
        key="toggle_remaining_time",
        use_container_width=True,
    ):
        st.session_state["hide_remaining_time"] = not hidden
        st.rerun()


def render_status_value(phase: str, language: str) -> None:
    chip_class = phase_class(phase)
    st.markdown(
        f"""
        <div style="font-size: 0.875rem; margin-bottom: 0.25rem;">{text("status", language)}</div>
        <div class="phase-chip {chip_class}">{text(phase, language)}</div>
        """,
        unsafe_allow_html=True,
    )


def render_timer_controls(timezone: str, language: str) -> bool:
    timer = timer_state.get_timer()
    phase = timer.get("phase")
    active = timer.get("active", False)

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        action_taken = False
        if col1.button(
            text("pause", language),
            disabled=not active or phase not in {"focus", "break"},
            use_container_width=True,
        ):
            timer_state.pause_session(timezone)
            action_taken = True
        if col2.button(
            text("resume", language),
            disabled=not active or phase != "paused",
            use_container_width=True,
        ):
            timer_state.resume_session(timezone)
            action_taken = True
        if col3.button(text("stop", language), disabled=not active, use_container_width=True):
            request_alarm_stop()
            timer_state.stop_session(timezone)
            action_taken = True
        return action_taken


def build_manual_schedule(
    total_focus_minutes: int,
    segment_focus_minutes: int,
    break_minutes: int,
) -> dict[str, float | int]:
    segment_focus_minutes = max(1, int(segment_focus_minutes))
    total_focus_minutes = max(1, int(total_focus_minutes))
    return {
        "planned_segments": (total_focus_minutes + segment_focus_minutes - 1) // segment_focus_minutes,
        "total_focus_seconds": total_focus_minutes * 60,
        "segment_focus_seconds": segment_focus_minutes * 60,
        "break_seconds": max(0, int(break_minutes)) * 60,
    }


def build_auto_schedule(
    total_time_minutes: int,
    planned_segments: int,
    total_break_minutes: int,
) -> dict[str, float | int]:
    planned_segments = max(1, int(planned_segments))
    total_seconds = max(1, int(total_time_minutes)) * 60
    max_segments_by_time = max(1, total_seconds // 60)
    planned_segments = min(planned_segments, max_segments_by_time)
    requested_total_break_seconds = max(0, int(total_break_minutes)) * 60
    break_count = max(0, planned_segments - 1)
    min_focus_seconds = planned_segments * 60
    actual_total_break_seconds = min(requested_total_break_seconds, max(0, total_seconds - min_focus_seconds))
    break_seconds = actual_total_break_seconds / break_count if break_count else 0
    total_focus_seconds = max(min_focus_seconds, total_seconds - (break_seconds * break_count))
    return {
        "planned_segments": planned_segments,
        "total_focus_seconds": total_focus_seconds,
        "segment_focus_seconds": total_focus_seconds / planned_segments,
        "break_seconds": break_seconds,
        "requested_total_break_seconds": requested_total_break_seconds,
        "actual_total_break_seconds": actual_total_break_seconds,
    }


def render_start_form(timezone: str, language: str) -> None:
    st.markdown(f"<h2>{text('start_title', language)}</h2>", unsafe_allow_html=True)
    disabled = timer_state.is_active()

    with st.container(border=True):
        st.subheader(text("study_plan_setup", language))
        schedule_mode = st.radio(
            text("schedule_mode", language),
            SCHEDULE_MODES,
            format_func=lambda value: option_label("mode", value, language),
            horizontal=True,
            disabled=disabled,
            key="schedule_mode",
        )
        if schedule_mode == "manual":
            st.caption(text("manual_mode_hint", language))
            total_focus_minutes = st.number_input(
                text("total_focus_minutes", language),
                min_value=1,
                max_value=720,
                value=60,
                step=5,
                disabled=disabled,
                key="manual_total_focus_minutes",
            )
            segment_focus_minutes = st.number_input(
                text("segment_focus_minutes", language),
                min_value=1,
                max_value=240,
                value=25,
                step=5,
                disabled=disabled,
                key="manual_segment_focus_minutes",
            )
            break_minutes = st.number_input(
                text("break_minutes", language),
                min_value=0,
                max_value=120,
                value=10,
                step=5,
                disabled=disabled,
                key="manual_break_minutes",
            )
            schedule = build_manual_schedule(
                int(total_focus_minutes),
                int(segment_focus_minutes),
                int(break_minutes),
            )
            st.caption(
                f"{text('planned_segments', language)}: {schedule['planned_segments']}. "
                f"{text('segmented_break_hint', language)}"
            )
        else:
            st.caption(text("auto_mode_hint", language))
            total_time_minutes = st.number_input(
                text("total_time_minutes", language),
                min_value=1,
                max_value=1440,
                value=120,
                step=5,
                disabled=disabled,
                key="auto_total_time_minutes",
            )
            planned_segments = st.number_input(
                text("auto_segments", language),
                min_value=1,
                max_value=48,
                value=4,
                step=1,
                disabled=disabled,
                key="auto_planned_segments",
            )
            total_break_minutes = st.number_input(
                text("total_break_minutes", language),
                min_value=0,
                max_value=1440,
                value=20,
                step=5,
                disabled=disabled,
                key="auto_total_break_minutes",
            )
            schedule = build_auto_schedule(
                int(total_time_minutes),
                int(planned_segments),
                int(total_break_minutes),
            )
            st.caption(
                f"{text('auto_total_focus', language)}: {timer_state.format_seconds(schedule['total_focus_seconds'])}\n\n"
                f"{text('auto_segment_focus', language)}: {timer_state.format_seconds(schedule['segment_focus_seconds'])}\n\n"
                f"{text('auto_break_per_gap', language)}: {timer_state.format_seconds(schedule['break_seconds'])}"
            )
            if schedule["actual_total_break_seconds"] < schedule["requested_total_break_seconds"]:
                st.warning(text("auto_adjusted_break", language))

    with st.container(border=True):
        task_type = st.selectbox(
            text("task_type", language),
            TASK_TYPES,
            format_func=lambda value: option_label("task", value, language),
            disabled=disabled,
            key="task_type_select",
        )
        custom_task_type = ""
        if task_type == "other":
            custom_task_type = st.text_input(text("custom_task_type", language), disabled=disabled)

        with st.form("start_session_form", clear_on_submit=False):
            subject_col, book_col = st.columns(2)
            with subject_col:
                subject = st.text_input(text("subject", language), disabled=disabled)
            with book_col:
                book_or_course = st.text_input(text("book_or_course", language), disabled=disabled)
            chapter = st.text_input(text("chapter", language), disabled=disabled)
            plan_note = st.text_area(text("plan_note", language), disabled=disabled)
            submitted = st.form_submit_button(text("start", language), disabled=disabled, use_container_width=True)

    if submitted:
        request_alarm_stop()
        saved_task_type = custom_task_type.strip() if task_type == "other" and custom_task_type.strip() else task_type
        values = {
            "subject": subject.strip(),
            "book_or_course": book_or_course.strip(),
            "chapter": chapter.strip(),
            "task_type": saved_task_type,
            "proof_status": "",
            "schedule_mode": schedule_mode,
            "total_focus_seconds": schedule["total_focus_seconds"],
            "segment_focus_seconds": schedule["segment_focus_seconds"],
            "break_seconds": schedule["break_seconds"],
            "total_focus_minutes": round(float(schedule["total_focus_seconds"]) / 60, 2),
            "pomodoro_minutes": round(float(schedule["segment_focus_seconds"]) / 60, 2),
            "break_minutes": round(float(schedule["break_seconds"]) / 60, 2),
            "target_pomodoros": int(schedule["planned_segments"]),
            "plan_note": plan_note.strip(),
        }
        timer_state.start_session(values, timezone)
        st.rerun()


def render_today_page(db: SheetsDB, timezone: str, language: str) -> None:
    drain_pending_writes(db, language)
    today = local_today(timezone)
    df = db.get_study_sessions_df()
    summary = analytics.today_summary(df, today)

    st.markdown(f"<h2>{text('page_today', language)}</h2>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(f"<div class='subtle-card'>{text('summary', language)}</div>", unsafe_allow_html=True)
        render_metric_cards(
            [
                (text("today_focus_minutes", language), str(summary["focus_minutes"]), "專注"),
                (text("today_study_hours", language), str(summary["study_hours"]), "時數"),
                (text("today_pomodoros", language), str(summary["pomodoros"]), "番茄"),
            ]
        )

    st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
    st.subheader(text("today_subject_hours", language))
    st.dataframe(display_df(summary["subject_hours"], language), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
    st.subheader(text("today_records", language))
    records = summary["records"]
    st.dataframe(display_df(records, language), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if records.empty:
        st.info(text("no_records_today", language))
        return

    st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
    st.subheader(text("edit_record", language))
    record_ids = records["id"].astype(str).tolist()
    selected_id = st.selectbox(
        text("select_record", language),
        record_ids,
        format_func=lambda record_id: record_option_label(records, record_id, language),
    )
    selected_row = records[records["id"] == selected_id].iloc[0]

    with st.form("edit_today_record"):
        output = st.text_area(text("output", language), value=str(selected_row.get("output", "")))
        stuck = st.text_area(text("stuck", language), value=str(selected_row.get("stuck", "")))
        next_action = st.text_area(text("next_action", language), value=str(selected_row.get("next_action", "")))
        submitted = st.form_submit_button(text("save_changes", language))
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        db.update_session_fields(
            selected_id,
            {
                "output": output,
                "stuck": stuck,
                "next_action": next_action,
            },
            timezone=timezone,
        )
        st.success(text("updated", language))
        st.rerun()


def render_stats_page(db: SheetsDB, timezone: str, language: str) -> None:
    drain_pending_writes(db, language)
    today = local_today(timezone)
    df = db.get_study_sessions_df()
    summary = analytics.cumulative_summary(df, today)

    st.markdown(f"<h2>{text('page_stats', language)}</h2>", unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader(text("overall_progress", language))
        render_metric_cards(
            [
                (text("total_hours", language), str(summary["total_hours"]), "時數"),
                (text("total_pomodoros", language), str(summary["total_pomodoros"]), "番茄"),
                (text("avg_7", language), str(summary["average_7_days"]), "週均"),
                (text("avg_30", language), str(summary["average_30_days"]), "月均"),
            ]
        )

    col_left, col_right = st.columns(2)
    with col_left:
        with st.container(border=True):
            st.subheader(text("subject_hours", language))
            st.dataframe(display_df(summary["subject_hours"], language), use_container_width=True, hide_index=True)
    with col_right:
        with st.container(border=True):
            st.subheader(text("task_type_hours", language))
            st.dataframe(display_df(summary["task_type_hours"], language), use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.subheader(text("daily_range_chart", language))
        default_start = today - timedelta(days=6)
        range_col_1, range_col_2 = st.columns(2)
        with range_col_1:
            start_date = st.date_input(
                text("chart_start_date", language),
                value=default_start,
                key="stats_chart_start_date",
            )
        with range_col_2:
            end_date = st.date_input(
                text("chart_end_date", language),
                value=today,
                key="stats_chart_end_date",
            )
        if start_date > end_date:
            st.warning(text("date_range_swapped", language))
            start_date, end_date = end_date, start_date
        range_daily_hours = daily_hours_between_compat(summary["counted"], start_date, end_date)
        chart_title = "Daily Focus Time by Date"
        chart_x_label = "Date"
        chart_y_label = "Focus hours (h)"
        chart_empty_label = "No data in selected range"
        st.pyplot(
            daily_hours_bar_figure_compat(
                range_daily_hours,
                title=chart_title,
                x_label=chart_x_label,
                y_label=chart_y_label,
                empty_label=chart_empty_label,
            )
        )

    with st.container(border=True):
        st.subheader(text("weekly_table", language))
        st.dataframe(display_df(summary["weekly_hours"], language), use_container_width=True, hide_index=True)


def render_search_page(db: SheetsDB, timezone: str, language: str) -> None:
    drain_pending_writes(db, language)
    df = db.get_study_sessions_df()

    st.markdown(f"<h2>{text('page_search', language)}</h2>", unsafe_allow_html=True)

    filters = {}
    with st.expander(text("filters", language), expanded=True):
        rows = [st.columns(4), st.columns(4)]
        for index, field in enumerate(SEARCH_FIELDS):
            with rows[index // 4][index % 4]:
                filters[field] = st.text_input(column_label(field, language))

    results = analytics.search_sessions(df, filters)
    with st.container(border=True):
        st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
        st.metric(text("search_results", language), len(results))
        st.dataframe(display_df(results, language), use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if results.empty:
        return

    st.markdown("<div class='subtle-card'>", unsafe_allow_html=True)
    st.subheader(text("edit_search_record", language))
    result_ids = results["id"].astype(str).tolist()
    selected_state = st.session_state.get("search_selected_record")
    selected_index = result_ids.index(selected_state) if selected_state in result_ids else 0
    selected_id = st.selectbox(
        text("select_record", language),
        result_ids,
        index=selected_index,
        format_func=lambda record_id: record_option_label(results, record_id, language),
        key="search_selected_record",
    )
    selected_row = results[results["id"].astype(str) == str(selected_id)].iloc[0]

    current_task_type = scalar_text(selected_row.get("task_type")) or "other"
    task_type_value = current_task_type if current_task_type in TASK_TYPES else "other"
    current_status = scalar_text(selected_row.get("status")) or "completed"
    status_options = list(SESSION_STATUS_OPTIONS)
    if current_status not in status_options:
        status_options.append(current_status)

    with st.form(f"edit_search_record_{selected_id}"):
        date_col, time_col_1, time_col_2 = st.columns(3)
        with date_col:
            record_date = st.date_input(
                column_label("date", language),
                value=scalar_date(selected_row.get("date"), local_today(timezone)),
            )
        with time_col_1:
            start_time = st.text_input(column_label("start_time", language), value=scalar_text(selected_row.get("start_time")))
        with time_col_2:
            end_time = st.text_input(column_label("end_time", language), value=scalar_text(selected_row.get("end_time")))

        subject_col, book_col = st.columns(2)
        with subject_col:
            subject = st.text_input(column_label("subject", language), value=scalar_text(selected_row.get("subject")))
        with book_col:
            book_or_course = st.text_input(
                column_label("book_or_course", language),
                value=scalar_text(selected_row.get("book_or_course")),
            )

        chapter = st.text_input(column_label("chapter", language), value=scalar_text(selected_row.get("chapter")))
        task_type = st.selectbox(
            column_label("task_type", language),
            TASK_TYPES,
            index=TASK_TYPES.index(task_type_value),
            format_func=lambda value: option_label("task", value, language),
        )
        custom_task_type = ""
        if task_type == "other":
            custom_task_type = st.text_input(
                text("custom_task_type", language),
                value="" if current_task_type in TASK_TYPES else current_task_type,
            )

        metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
        with metric_col_1:
            focus_minutes = st.number_input(
                column_label("focus_minutes", language),
                min_value=0.0,
                value=scalar_float(selected_row.get("focus_minutes")),
                step=1.0,
            )
        with metric_col_2:
            break_minutes = st.number_input(
                column_label("break_minutes", language),
                min_value=0.0,
                value=scalar_float(selected_row.get("break_minutes")),
                step=1.0,
            )
        with metric_col_3:
            completed_pomodoros = st.number_input(
                column_label("completed_pomodoros", language),
                min_value=0,
                value=scalar_int(selected_row.get("completed_pomodoros")),
                step=1,
            )
        with metric_col_4:
            pomodoro_minutes = st.number_input(
                column_label("pomodoro_minutes", language),
                min_value=0.0,
                value=scalar_float(selected_row.get("pomodoro_minutes")),
                step=1.0,
            )

        status = st.selectbox(
            column_label("status", language),
            status_options,
            index=status_options.index(current_status),
            format_func=lambda value: text(str(value), language),
        )
        plan_note = st.text_area(column_label("plan_note", language), value=scalar_text(selected_row.get("plan_note")))
        output = st.text_area(column_label("output", language), value=scalar_text(selected_row.get("output")))
        stuck = st.text_area(column_label("stuck", language), value=scalar_text(selected_row.get("stuck")))
        next_action = st.text_area(column_label("next_action", language), value=scalar_text(selected_row.get("next_action")))
        edit_submitted = st.form_submit_button(text("save_changes", language), use_container_width=True)

    if edit_submitted:
        saved_task_type = custom_task_type.strip() if task_type == "other" and custom_task_type.strip() else task_type
        db.update_session_fields(
            selected_id,
            {
                "date": record_date.isoformat(),
                "start_time": start_time.strip(),
                "end_time": end_time.strip(),
                "subject": subject.strip(),
                "book_or_course": book_or_course.strip(),
                "chapter": chapter.strip(),
                "task_type": saved_task_type,
                "plan_note": plan_note.strip(),
                "focus_minutes": round(float(focus_minutes), 2),
                "break_minutes": round(float(break_minutes), 2),
                "completed_pomodoros": int(completed_pomodoros),
                "pomodoro_minutes": round(float(pomodoro_minutes), 2),
                "status": status,
                "output": output.strip(),
                "stuck": stuck.strip(),
                "next_action": next_action.strip(),
            },
            timezone=timezone,
        )
        st.success(text("updated", language))
        st.rerun()

    with st.form(f"delete_search_record_{selected_id}"):
        st.warning(text("delete_record_warning", language))
        confirm_delete = st.checkbox(text("confirm_delete", language))
        delete_submitted = st.form_submit_button(text("delete_record", language), use_container_width=True)

    if delete_submitted:
        if not confirm_delete:
            st.error(text("confirm_delete_first", language))
        else:
            delete_session_compat(db, selected_id)
            st.success(text("deleted", language))
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_export_page(db: SheetsDB, timezone: str, language: str) -> None:
    drain_pending_writes(db, language)
    today = local_today(timezone)
    df = db.get_study_sessions_df()
    weekly = analytics.weekly_hours(analytics.counted_sessions(df))
    subject_stats = analytics.cumulative_summary(df, today)["subject_hours"]

    st.markdown(f"<h2>{text('page_export', language)}</h2>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(f"<div class='subtle-card'>{text('csv_export', language)}</div>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                text("all_records_csv", language),
                data=export.all_records_csv(df),
                file_name="study_sessions_all.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                text("today_records_csv", language),
                data=export.today_records_csv(df, today),
                file_name=f"study_sessions_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                text("weekly_summary_csv", language),
                data=export.csv_bytes(weekly),
                file_name="weekly_summary.csv",
                mime="text/csv",
                use_container_width=True,
            )
            st.download_button(
                text("subject_stats_csv", language),
                data=export.csv_bytes(subject_stats),
                file_name="subject_stats.csv",
                mime="text/csv",
                use_container_width=True,
            )


def display_df(df: pd.DataFrame, language: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy()
    drop_columns = [column for column in HIDDEN_DISPLAY_COLUMNS | {"proof_status"} if column in result.columns]
    if drop_columns:
        result = result.drop(columns=drop_columns)
    if "status" in result.columns:
        result["status"] = result["status"].map(lambda value: text(str(value), language))
    if "task_type" in result.columns:
        result["task_type"] = result["task_type"].map(lambda value: option_label("task", str(value), language))
    for column in result.columns:
        result[column] = result[column].astype(str)
    labels = COLUMN_LABELS.get(language, {})
    if labels:
        result = result.rename(columns={column: labels.get(column, column) for column in result.columns})
    return result


if __name__ == "__main__":
    main()





