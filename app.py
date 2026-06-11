from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

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


st.set_page_config(page_title="讀書番茄鐘紀錄系統", layout="wide")


@st.cache_resource(show_spinner=False)
def get_db(sheet_id: str, credentials_json: str) -> SheetsDB:
    return SheetsDB(sheet_id, json.loads(credentials_json))


def local_today(timezone: str):
    return datetime.now(ZoneInfo(timezone)).date()


def local_now_iso(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat()


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
        st.error("Google Sheets 連線失敗。請確認 Sheet ID、service account secrets，以及 Sheet 分享權限。")
        st.exception(exc)
        st.stop()
    timer_state.init_timer_state()

    st.title("讀書番茄鐘紀錄系統")
    page = st.sidebar.radio(
        "頁面",
        ["開始讀書", "今日紀錄", "累積統計", "搜尋", "匯出"],
    )

    if page == "開始讀書":
        render_start_page(db, config.timezone)
    elif page == "今日紀錄":
        render_today_page(db, config.timezone)
    elif page == "累積統計":
        render_stats_page(db, config.timezone)
    elif page == "搜尋":
        render_search_page(db)
    elif page == "匯出":
        render_export_page(db, config.timezone)


def drain_pending_writes(db: SheetsDB) -> None:
    for event in timer_state.pending_pomodoro_events():
        try:
            db.upsert_pomodoro_event(event)
            timer_state.mark_pomodoro_event_saved(event["id"])
        except Exception as exc:
            st.error(f"寫入 pomodoro_events 失敗：{exc}")
            return

    record = timer_state.pending_session_record()
    if record:
        try:
            db.upsert_study_session(record)
            timer_state.mark_session_record_saved()
        except Exception as exc:
            st.error(f"寫入 study_sessions 失敗：{exc}")


def render_start_page(db: SheetsDB, timezone: str) -> None:
    if timer_state.is_running() and st_autorefresh:
        st_autorefresh(interval=1000, key="timer_refresh")

    timer_state.advance_timer(timezone)
    drain_pending_writes(db)

    left, right = st.columns([1.1, 1])
    with left:
        render_timer_panel(timezone)
        action_taken = render_timer_controls(timezone)
        drain_pending_writes(db)
        if action_taken:
            st.rerun()

    with right:
        render_start_form(timezone)

    if timer_state.is_running() and not st_autorefresh:
        st.info("若倒數畫面沒有自動更新，請安裝 requirements.txt 內的 streamlit-autorefresh。")


def render_timer_panel(timezone: str) -> None:
    timer = timer_state.get_timer()
    snap = timer_state.snapshot(timezone)
    phase_labels = {
        "idle": "未開始",
        "focus": "專注中",
        "break": "休息中",
        "paused": "已暫停",
        "completed": "已完成",
        "saved_partial": "已儲存部分紀錄",
        "stopped": "已停止",
    }

    st.subheader("目前計時")
    phase = snap.get("phase", "idle")
    st.metric("狀態", phase_labels.get(phase, phase))

    if snap.get("active"):
        st.metric("剩餘時間", timer_state.format_seconds(snap["remaining_seconds"]))
        st.progress(float(snap["progress"]))
        col1, col2, col3 = st.columns(3)
        col1.metric("已專注分鐘", snap["focus_minutes"])
        col2.metric(
            "番茄鐘",
            f'{snap["completed_pomodoros"]} / {snap["target_pomodoros"]}',
        )
        col3.metric("休息分鐘", snap.get("break_elapsed_minutes", 0))
        st.caption(
            f'{snap.get("subject", "")} / {snap.get("book_or_course", "")} / {snap.get("chapter", "")}'
        )
    else:
        st.metric("剩餘時間", "00:00")
        st.progress(0.0)
        if timer.get("saved_message"):
            st.success(f"上次狀態：{phase_labels.get(timer['saved_message'], timer['saved_message'])}")


def render_timer_controls(timezone: str) -> bool:
    timer = timer_state.get_timer()
    phase = timer.get("phase")
    active = timer.get("active", False)

    col1, col2, col3 = st.columns(3)
    action_taken = False
    if col1.button("Pause", disabled=not active or phase not in {"focus", "break"}, use_container_width=True):
        timer_state.pause_session(timezone)
        action_taken = True
    if col2.button("Resume", disabled=not active or phase != "paused", use_container_width=True):
        timer_state.resume_session(timezone)
        action_taken = True
    if col3.button("Stop", disabled=not active, use_container_width=True):
        timer_state.stop_session(timezone)
        action_taken = True
    col4, col5 = st.columns(2)
    if col4.button("Complete manually", disabled=not active, use_container_width=True):
        timer_state.complete_manually(timezone)
        action_taken = True
    if col5.button("Save partial session", disabled=not active, use_container_width=True):
        timer_state.save_partial_session(timezone)
        action_taken = True
    return action_taken


def render_start_form(timezone: str) -> None:
    st.subheader("開始讀書")
    disabled = timer_state.is_active()
    with st.form("start_session_form", clear_on_submit=False):
        subject = st.text_input("subject", disabled=disabled)
        book_or_course = st.text_input("book_or_course", disabled=disabled)
        chapter = st.text_input("chapter", disabled=disabled)
        task_type = st.text_input("task_type", disabled=disabled)
        proof_status = st.text_input("proof_status", disabled=disabled)
        pomodoro_minutes = st.number_input(
            "pomodoro_minutes",
            min_value=1,
            max_value=240,
            value=60,
            step=5,
            disabled=disabled,
        )
        break_minutes = st.number_input(
            "break_minutes",
            min_value=0,
            max_value=120,
            value=10,
            step=5,
            disabled=disabled,
        )
        target_pomodoros = st.number_input(
            "target_pomodoros",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            disabled=disabled,
        )
        plan_note = st.text_area("plan_note", disabled=disabled)
        submitted = st.form_submit_button("Start", disabled=disabled)

    if submitted:
        values = {
            "subject": subject.strip(),
            "book_or_course": book_or_course.strip(),
            "chapter": chapter.strip(),
            "task_type": task_type.strip(),
            "proof_status": proof_status.strip(),
            "pomodoro_minutes": int(pomodoro_minutes),
            "break_minutes": int(break_minutes),
            "target_pomodoros": int(target_pomodoros),
            "plan_note": plan_note.strip(),
        }
        timer_state.start_session(values, timezone)
        st.rerun()


def render_today_page(db: SheetsDB, timezone: str) -> None:
    today = local_today(timezone)
    df = db.get_study_sessions_df()
    summary = analytics.today_summary(df, today)

    col1, col2, col3 = st.columns(3)
    col1.metric("今日專注分鐘", summary["focus_minutes"])
    col2.metric("今日讀書時數", summary["study_hours"])
    col3.metric("今日番茄鐘數", summary["pomodoros"])

    st.subheader("今日各科時數")
    st.dataframe(summary["subject_hours"], use_container_width=True, hide_index=True)

    st.subheader("今日所有紀錄")
    records = summary["records"]
    st.dataframe(display_df(records), use_container_width=True, hide_index=True)

    if records.empty:
        return

    st.subheader("補填或修改")
    labels = records.apply(
        lambda row: f"{row['start_time']} | {row['subject']} | {row['book_or_course']} | {row['status']} | {row['id']}",
        axis=1,
    ).tolist()
    selected = st.selectbox("選擇紀錄", labels)
    selected_id = selected.split(" | ")[-1]
    selected_row = records[records["id"] == selected_id].iloc[0]

    with st.form("edit_today_record"):
        output = st.text_area("output 今日產出", value=str(selected_row.get("output", "")))
        stuck = st.text_area("stuck 卡住問題", value=str(selected_row.get("stuck", "")))
        next_action = st.text_area("next_action 下次第一件事", value=str(selected_row.get("next_action", "")))
        proof_status = st.text_input(
            "proof_status 證明掌握程度",
            value=str(selected_row.get("proof_status", "")),
        )
        submitted = st.form_submit_button("儲存修改")

    if submitted:
        db.update_session_fields(
            selected_id,
            {
                "output": output,
                "stuck": stuck,
                "next_action": next_action,
                "proof_status": proof_status,
            },
            timezone=timezone,
        )
        st.success("已更新。")
        st.rerun()


def render_stats_page(db: SheetsDB, timezone: str) -> None:
    today = local_today(timezone)
    df = db.get_study_sessions_df()
    summary = analytics.cumulative_summary(df, today)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("總累積時數", summary["total_hours"])
    col2.metric("總番茄鐘數", summary["total_pomodoros"])
    col3.metric("最近 7 日平均時數", summary["average_7_days"])
    col4.metric("最近 30 日平均時數", summary["average_30_days"])

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("各科累積時數")
        st.dataframe(summary["subject_hours"], use_container_width=True, hide_index=True)
    with col_right:
        st.subheader("各任務類型累積時數")
        st.dataframe(summary["task_type_hours"], use_container_width=True, hide_index=True)

    st.subheader("每日讀書時數折線圖")
    st.pyplot(analytics.daily_hours_figure(summary["daily_hours"]))

    st.subheader("每週讀書時數表")
    st.dataframe(summary["weekly_hours"], use_container_width=True, hide_index=True)


def render_search_page(db: SheetsDB) -> None:
    df = db.get_study_sessions_df()
    fields = [
        "subject",
        "book_or_course",
        "chapter",
        "task_type",
        "output",
        "stuck",
        "next_action",
        "proof_status",
    ]

    filters = {}
    rows = [st.columns(4), st.columns(4)]
    for index, field in enumerate(fields):
        with rows[index // 4][index % 4]:
            filters[field] = st.text_input(field)

    results = analytics.search_sessions(df, filters)
    st.metric("搜尋結果筆數", len(results))
    st.dataframe(display_df(results), use_container_width=True, hide_index=True)


def render_export_page(db: SheetsDB, timezone: str) -> None:
    today = local_today(timezone)
    df = db.get_study_sessions_df()
    weekly = analytics.weekly_hours(analytics.counted_sessions(df))
    subject_stats = analytics.cumulative_summary(df, today)["subject_hours"]

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "全部紀錄 CSV",
            data=export.all_records_csv(df),
            file_name="study_sessions_all.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "今日紀錄 CSV",
            data=export.today_records_csv(df, today),
            file_name=f"study_sessions_{today}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "每週摘要 CSV",
            data=export.csv_bytes(weekly),
            file_name="weekly_summary.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "各科統計 CSV",
            data=export.csv_bytes(subject_stats),
            file_name="subject_stats.csv",
            mime="text/csv",
            use_container_width=True,
        )


def display_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    result = df.copy()
    for column in result.columns:
        result[column] = result[column].astype(str)
    return result


if __name__ == "__main__":
    main()
