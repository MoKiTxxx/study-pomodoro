from __future__ import annotations

import json
import base64
from datetime import datetime
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


st.set_page_config(page_title="Study Pomodoro Tracker", layout="wide", initial_sidebar_state="expanded")

ALARM_PATH = Path(__file__).with_name("Alarm.mp3")
ALARM_PLAY_SECONDS = 8

# Streamlit's built-in toolbar is not localized by the app language switch.
st.markdown(
    """
    <style>
    #MainMenu,
    [data-testid="stDeployButton"],
    [data-testid="stDecoration"],
    footer {
        display: none !important;
        visibility: hidden !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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

PROOF_STATUSES = [
    "not_started",
    "understood",
    "can_recall",
    "can_solve",
    "can_explain",
    "needs_review",
]

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
    },
}

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


def option_label(prefix: str, value: str, language: str) -> str:
    key = f"{prefix}_{value}"
    translated = text(key, language)
    return value if translated == key else translated


def page_label(page_key: str, language: str) -> str:
    return text(f"page_{page_key}", language)


def main() -> None:
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
        render_search_page(db, language)
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


def render_start_page(db: SheetsDB, timezone: str, language: str) -> None:
    timer_state.advance_timer(timezone)
    alarm_refresh_token = render_alarm_player()
    just_finished = timer_state.consume_just_finished()

    if just_finished:
        if st_autorefresh and not alarm_refresh_token:
            st_autorefresh(interval=600, limit=1, key="write_after_finish")
    else:
        drain_pending_writes(db, language)

    if alarm_refresh_token and st_autorefresh:
        st_autorefresh(
            interval=ALARM_PLAY_SECONDS * 1000,
            limit=1,
            key=f"alarm_refresh_{alarm_refresh_token}",
        )
    elif timer_state.is_running() and st_autorefresh:
        st_autorefresh(interval=500, key="timer_refresh")

    show_timer = timer_state.is_active() or timer_state.get_timer().get("phase") in {
        "completed",
        "saved_partial",
        "stopped",
        "paused",
    }

    if show_timer:
        render_timer_panel(timezone, language)
        action_taken = render_timer_controls(timezone, language)
        if action_taken:
            st.rerun()
        if timer_state.has_pending_writes():
            st.info(text("syncing", language))
        if not timer_state.is_active():
            if st.button(text("new_session", language), use_container_width=True):
                timer_state.reset_timer_state()
                st.rerun()
    else:
        render_start_form(timezone, language)

    if timer_state.is_running() and not st_autorefresh:
        st.info(text("no_autorefresh", language))


def render_timer_panel(timezone: str, language: str) -> None:
    timer = timer_state.get_timer()
    snap = timer_state.snapshot(timezone)

    st.subheader(text("timer_title", language))
    phase = snap.get("phase", "idle")
    render_status_value(phase, language)

    if snap.get("active"):
        render_remaining_time(timer_state.format_seconds(snap["remaining_seconds"]), language)
        st.progress(float(snap["progress"]))
        col1, col2, col3 = st.columns(3)
        col1.metric(text("focused_time", language), timer_state.format_seconds(snap["focus_seconds"]))
        col2.metric(
            text("pomodoros", language),
            f'{snap["completed_pomodoros"]} / {snap["target_pomodoros"]}',
        )
        col3.metric(
            text("break_time", language),
            timer_state.format_seconds(snap.get("break_elapsed_seconds", 0)),
        )
        st.caption(
            f'{snap.get("subject", "")} / {snap.get("book_or_course", "")} / {snap.get("chapter", "")}'
        )
    else:
        render_remaining_time("00:00:00", language)
        st.progress(0.0)
        col1, col2, col3 = st.columns(3)
        col1.metric(text("focused_time", language), timer_state.format_seconds(snap.get("focus_seconds", 0)))
        col2.metric(
            text("pomodoros", language),
            f'{snap.get("completed_pomodoros", 0)} / {snap.get("target_pomodoros", 0)}',
        )
        col3.metric(
            text("break_time", language),
            timer_state.format_seconds(snap.get("break_elapsed_seconds", 0)),
        )
        if timer.get("saved_message"):
            st.success(f"{text('last_status', language)}：{text(timer['saved_message'], language)}")


def render_alarm_player() -> int | None:
    alarm_count = timer_state.consume_pending_alarm_count()
    if alarm_count <= 0 or not ALARM_PATH.exists():
        return None

    token = int(st.session_state.get("alarm_refresh_token", 0)) + 1
    st.session_state["alarm_refresh_token"] = token
    audio_data = base64.b64encode(ALARM_PATH.read_bytes()).decode("ascii")
    components.html(
        f"""
        <audio id="pomodoro-alarm" autoplay style="display: none;">
            <source src="data:audio/mpeg;base64,{audio_data}" type="audio/mpeg">
        </audio>
        <script>
        const alarm = document.getElementById("pomodoro-alarm");
        if (alarm) {{
            alarm.volume = 1;
            alarm.play().catch(() => {{}});
        }}
        </script>
        """,
        height=0,
    )
    return token


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
    color = "#22c55e" if phase in {"focus", "break"} else "inherit"
    st.markdown(
        f"""
        <div style="font-size: 0.875rem; margin-bottom: 0.25rem;">{text("status", language)}</div>
        <div style="font-size: 2.25rem; line-height: 1.15; font-weight: 500; color: {color};">
            {text(phase, language)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_timer_controls(timezone: str, language: str) -> bool:
    timer = timer_state.get_timer()
    phase = timer.get("phase")
    active = timer.get("active", False)

    col1, col2, col3 = st.columns(3)
    action_taken = False
    if col1.button(text("pause", language), disabled=not active or phase not in {"focus", "break"}, use_container_width=True):
        timer_state.pause_session(timezone)
        action_taken = True
    if col2.button(text("resume", language), disabled=not active or phase != "paused", use_container_width=True):
        timer_state.resume_session(timezone)
        action_taken = True
    if col3.button(text("stop", language), disabled=not active, use_container_width=True):
        timer_state.stop_session(timezone)
        action_taken = True
    return action_taken


def render_start_form(timezone: str, language: str) -> None:
    st.subheader(text("start_title", language))
    disabled = timer_state.is_active()
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
        planned_segments = (int(total_focus_minutes) + int(segment_focus_minutes) - 1) // int(segment_focus_minutes)
        total_focus_seconds = int(total_focus_minutes) * 60
        segment_focus_seconds = int(segment_focus_minutes) * 60
        break_seconds = int(break_minutes) * 60
        st.caption(f"{text('planned_segments', language)}: {planned_segments}. {text('segmented_break_hint', language)}")
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
        total_seconds = int(total_time_minutes) * 60
        requested_total_break_seconds = int(total_break_minutes) * 60
        break_count = max(0, int(planned_segments) - 1)
        min_focus_seconds = int(planned_segments)
        actual_total_break_seconds = min(requested_total_break_seconds, max(0, total_seconds - min_focus_seconds))
        break_seconds = actual_total_break_seconds / break_count if break_count else 0
        break_total_seconds = break_seconds * break_count
        total_focus_seconds = max(min_focus_seconds, total_seconds - break_total_seconds)
        segment_focus_seconds = total_focus_seconds / int(planned_segments) if planned_segments else 0
        st.caption(
            f"{text('auto_total_focus', language)}: {timer_state.format_seconds(int(total_focus_seconds))}\n\n"
            f"{text('auto_segment_focus', language)}: {timer_state.format_seconds(round(segment_focus_seconds))}\n\n"
            f"{text('auto_break_per_gap', language)}: {timer_state.format_seconds(round(break_seconds))}"
        )
        if actual_total_break_seconds < requested_total_break_seconds:
            st.warning(text("auto_adjusted_break", language))

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
        submitted = st.form_submit_button(text("start", language), disabled=disabled)

    if submitted:
        saved_task_type = custom_task_type.strip() if task_type == "other" and custom_task_type.strip() else task_type
        values = {
            "subject": subject.strip(),
            "book_or_course": book_or_course.strip(),
            "chapter": chapter.strip(),
            "task_type": saved_task_type,
            "proof_status": "",
            "schedule_mode": schedule_mode,
            "total_focus_seconds": total_focus_seconds,
            "segment_focus_seconds": segment_focus_seconds,
            "break_seconds": break_seconds,
            "total_focus_minutes": round(total_focus_seconds / 60, 2),
            "pomodoro_minutes": round(segment_focus_seconds / 60, 2),
            "break_minutes": round(break_seconds / 60, 2),
            "target_pomodoros": int(planned_segments),
            "plan_note": plan_note.strip(),
        }
        timer_state.start_session(values, timezone)
        st.rerun()


def render_today_page(db: SheetsDB, timezone: str, language: str) -> None:
    drain_pending_writes(db, language)
    today = local_today(timezone)
    df = db.get_study_sessions_df()
    summary = analytics.today_summary(df, today)

    col1, col2, col3 = st.columns(3)
    col1.metric(text("today_focus_minutes", language), summary["focus_minutes"])
    col2.metric(text("today_study_hours", language), summary["study_hours"])
    col3.metric(text("today_pomodoros", language), summary["pomodoros"])

    st.subheader(text("today_subject_hours", language))
    st.dataframe(display_df(summary["subject_hours"], language), use_container_width=True, hide_index=True)

    st.subheader(text("today_records", language))
    records = summary["records"]
    st.dataframe(display_df(records, language), use_container_width=True, hide_index=True)

    if records.empty:
        return

    st.subheader(text("edit_record", language))
    labels = records.apply(
        lambda row: f"{row['start_time']} | {row['subject']} | {row['book_or_course']} | {row['status']} | {row['id']}",
        axis=1,
    ).tolist()
    selected = st.selectbox(text("select_record", language), labels)
    selected_id = selected.split(" | ")[-1]
    selected_row = records[records["id"] == selected_id].iloc[0]

    with st.form("edit_today_record"):
        output = st.text_area(text("output", language), value=str(selected_row.get("output", "")))
        stuck = st.text_area(text("stuck", language), value=str(selected_row.get("stuck", "")))
        next_action = st.text_area(text("next_action", language), value=str(selected_row.get("next_action", "")))
        submitted = st.form_submit_button(text("save_changes", language))

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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(text("total_hours", language), summary["total_hours"])
    col2.metric(text("total_pomodoros", language), summary["total_pomodoros"])
    col3.metric(text("avg_7", language), summary["average_7_days"])
    col4.metric(text("avg_30", language), summary["average_30_days"])

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader(text("subject_hours", language))
        st.dataframe(display_df(summary["subject_hours"], language), use_container_width=True, hide_index=True)
    with col_right:
        st.subheader(text("task_type_hours", language))
        st.dataframe(display_df(summary["task_type_hours"], language), use_container_width=True, hide_index=True)

    st.subheader(text("daily_line", language))
    st.pyplot(
        analytics.daily_hours_figure(
            summary["daily_hours"],
            title=text("chart_title", language),
            x_label=text("chart_x", language),
            y_label=text("chart_y", language),
            empty_label=text("chart_empty", language),
        )
    )

    st.subheader(text("weekly_table", language))
    st.dataframe(display_df(summary["weekly_hours"], language), use_container_width=True, hide_index=True)


def render_search_page(db: SheetsDB, language: str) -> None:
    drain_pending_writes(db, language)
    df = db.get_study_sessions_df()
    fields = [
        "subject",
        "book_or_course",
        "chapter",
        "task_type",
        "output",
        "stuck",
        "next_action",
    ]

    filters = {}
    rows = [st.columns(4), st.columns(4)]
    for index, field in enumerate(fields):
        with rows[index // 4][index % 4]:
            filters[field] = st.text_input(COLUMN_LABELS.get(language, {}).get(field, field))

    results = analytics.search_sessions(df, filters)
    st.metric(text("search_results", language), len(results))
    st.dataframe(display_df(results, language), use_container_width=True, hide_index=True)


def render_export_page(db: SheetsDB, timezone: str, language: str) -> None:
    drain_pending_writes(db, language)
    today = local_today(timezone)
    df = db.get_study_sessions_df()
    weekly = analytics.weekly_hours(analytics.counted_sessions(df))
    subject_stats = analytics.cumulative_summary(df, today)["subject_hours"]

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
    if "proof_status" in result.columns:
        result = result.drop(columns=["proof_status"])
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
