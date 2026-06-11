from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st


TIMER_KEY = "timer"


def now_in_timezone(timezone: str) -> datetime:
    return datetime.now(ZoneInfo(timezone))


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _seconds_between(start_iso: str, end: datetime) -> float:
    return max(0.0, (end - _dt(start_iso)).total_seconds())


def _time_text(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


def _date_text(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def init_timer_state() -> None:
    if TIMER_KEY not in st.session_state:
        st.session_state[TIMER_KEY] = {
            "active": False,
            "phase": "idle",
            "pending_pomodoro_events": [],
            "pending_session_record": None,
            "saved_message": "",
        }


def get_timer() -> dict[str, Any]:
    init_timer_state()
    return st.session_state[TIMER_KEY]


def is_running() -> bool:
    timer = get_timer()
    return bool(timer.get("active")) and timer.get("phase") in {"focus", "break"}


def is_active() -> bool:
    timer = get_timer()
    return bool(timer.get("active"))


def start_session(values: dict[str, Any], timezone: str) -> None:
    started_at = now_in_timezone(timezone)
    session_id = str(uuid.uuid4())
    pomodoro_minutes = int(values["pomodoro_minutes"])
    break_minutes = int(values["break_minutes"])
    target_pomodoros = int(values["target_pomodoros"])

    st.session_state[TIMER_KEY] = {
        "active": True,
        "phase": "focus",
        "paused_phase": None,
        "session_id": session_id,
        "date": _date_text(started_at),
        "start_time": _time_text(started_at),
        "session_started_at": _iso(started_at),
        "phase_started_at": _iso(started_at),
        "focus_started_at": _iso(started_at),
        "subject": values["subject"],
        "book_or_course": values["book_or_course"],
        "chapter": values["chapter"],
        "task_type": values["task_type"],
        "proof_status": values["proof_status"],
        "plan_note": values["plan_note"],
        "pomodoro_minutes": pomodoro_minutes,
        "break_minutes": break_minutes,
        "target_pomodoros": target_pomodoros,
        "current_focus_seconds": 0.0,
        "current_break_seconds": 0.0,
        "total_focus_seconds": 0.0,
        "total_break_seconds": 0.0,
        "completed_pomodoros": 0,
        "pending_pomodoro_events": [],
        "pending_session_record": None,
        "saved_message": "",
    }


def pause_session(timezone: str) -> None:
    timer = get_timer()
    if not timer.get("active") or timer.get("phase") not in {"focus", "break"}:
        return

    current = now_in_timezone(timezone)
    phase = timer["phase"]
    elapsed = _seconds_between(timer["phase_started_at"], current)
    if phase == "focus":
        timer["total_focus_seconds"] += elapsed
        timer["current_focus_seconds"] += elapsed
    else:
        timer["total_break_seconds"] += elapsed
        timer["current_break_seconds"] += elapsed

    timer["phase"] = "paused"
    timer["paused_phase"] = phase
    timer["paused_at"] = _iso(current)


def resume_session(timezone: str) -> None:
    timer = get_timer()
    if not timer.get("active") or timer.get("phase") != "paused":
        return

    current = now_in_timezone(timezone)
    paused_phase = timer.get("paused_phase") or "focus"
    timer["phase"] = paused_phase
    timer["phase_started_at"] = _iso(current)
    timer["paused_phase"] = None
    timer.pop("paused_at", None)


def advance_timer(timezone: str) -> None:
    timer = get_timer()
    if not timer.get("active") or timer.get("phase") not in {"focus", "break"}:
        return

    current = now_in_timezone(timezone)
    max_transitions = max(4, int(timer.get("target_pomodoros", 1)) * 3)

    for _ in range(max_transitions):
        phase = timer.get("phase")
        if phase == "focus":
            pomodoro_seconds = int(timer["pomodoro_minutes"]) * 60
            elapsed = _seconds_between(timer["phase_started_at"], current)
            needed = max(0.0, pomodoro_seconds - float(timer["current_focus_seconds"]))
            if elapsed < needed:
                return

            completed_at = _dt(timer["phase_started_at"]) + timedelta(seconds=needed)
            timer["total_focus_seconds"] += needed
            timer["completed_pomodoros"] += 1
            timer["pending_pomodoro_events"].append(
                {
                    "id": str(uuid.uuid4()),
                    "session_id": timer["session_id"],
                    "date": timer["date"],
                    "start_time": _time_text(_dt(timer["focus_started_at"])),
                    "end_time": _time_text(completed_at),
                    "focus_minutes": int(timer["pomodoro_minutes"]),
                    "status": "completed",
                    "created_at": _iso(completed_at),
                }
            )

            timer["current_focus_seconds"] = 0.0
            if int(timer["completed_pomodoros"]) >= int(timer["target_pomodoros"]):
                _finish_session(timer, "completed", completed_at)
                return

            timer["phase"] = "break"
            timer["phase_started_at"] = _iso(completed_at)
            timer["current_break_seconds"] = 0.0
            continue

        if phase == "break":
            break_seconds = int(timer["break_minutes"]) * 60
            if break_seconds <= 0:
                break_ended_at = _dt(timer["phase_started_at"])
            else:
                elapsed = _seconds_between(timer["phase_started_at"], current)
                needed = max(0.0, break_seconds - float(timer["current_break_seconds"]))
                if elapsed < needed:
                    return
                break_ended_at = _dt(timer["phase_started_at"]) + timedelta(seconds=needed)
                timer["total_break_seconds"] += needed

            timer["phase"] = "focus"
            timer["phase_started_at"] = _iso(break_ended_at)
            timer["focus_started_at"] = _iso(break_ended_at)
            timer["current_break_seconds"] = 0.0
            timer["current_focus_seconds"] = 0.0
            continue

        return


def complete_manually(timezone: str) -> None:
    timer = get_timer()
    if not timer.get("active"):
        return
    current = _commit_active_phase_elapsed(timer, timezone)
    _finish_session(timer, "completed", current)


def save_partial_session(timezone: str) -> None:
    timer = get_timer()
    if not timer.get("active"):
        return
    current = _commit_active_phase_elapsed(timer, timezone)
    _finish_session(timer, "saved_partial", current)


def stop_session(timezone: str) -> None:
    timer = get_timer()
    if not timer.get("active"):
        return
    current = _commit_active_phase_elapsed(timer, timezone)
    _finish_session(timer, "stopped", current)


def _commit_active_phase_elapsed(timer: dict[str, Any], timezone: str) -> datetime:
    current = now_in_timezone(timezone)
    phase = timer.get("phase")
    if phase == "focus":
        elapsed = _seconds_between(timer["phase_started_at"], current)
        timer["total_focus_seconds"] += elapsed
        timer["current_focus_seconds"] += elapsed
    elif phase == "break":
        elapsed = _seconds_between(timer["phase_started_at"], current)
        timer["total_break_seconds"] += elapsed
        timer["current_break_seconds"] += elapsed
    return current


def _finish_session(timer: dict[str, Any], status: str, ended_at: datetime) -> None:
    timer["active"] = False
    timer["phase"] = status
    timer["pending_session_record"] = build_session_record(timer, status, ended_at)
    timer["saved_message"] = status


def build_session_record(timer: dict[str, Any], status: str, ended_at: datetime) -> dict[str, Any]:
    return {
        "id": timer["session_id"],
        "date": timer["date"],
        "start_time": timer["start_time"],
        "end_time": _time_text(ended_at),
        "subject": timer["subject"],
        "book_or_course": timer["book_or_course"],
        "chapter": timer["chapter"],
        "task_type": timer["task_type"],
        "proof_status": timer["proof_status"],
        "plan_note": timer["plan_note"],
        "focus_minutes": round(float(timer["total_focus_seconds"]) / 60, 2),
        "break_minutes": int(timer["break_minutes"]),
        "completed_pomodoros": int(timer["completed_pomodoros"]),
        "pomodoro_minutes": int(timer["pomodoro_minutes"]),
        "status": status,
        "output": "",
        "stuck": "",
        "next_action": "",
        "created_at": timer["session_started_at"],
        "updated_at": _iso(ended_at),
    }


def snapshot(timezone: str) -> dict[str, Any]:
    timer = get_timer()
    if not timer.get("active"):
        return {
            "active": False,
            "phase": timer.get("phase", "idle"),
            "focus_minutes": 0.0,
            "remaining_seconds": 0,
            "progress": 0.0,
            "completed_pomodoros": timer.get("completed_pomodoros", 0),
            "target_pomodoros": timer.get("target_pomodoros", 0),
        }

    current = now_in_timezone(timezone)
    phase = timer.get("phase")
    total_focus = float(timer["total_focus_seconds"])
    total_break = float(timer["total_break_seconds"])
    current_focus = float(timer["current_focus_seconds"])
    current_break = float(timer["current_break_seconds"])

    if phase == "focus":
        elapsed = _seconds_between(timer["phase_started_at"], current)
        total_focus += elapsed
        current_focus += elapsed
        duration = int(timer["pomodoro_minutes"]) * 60
        remaining = max(0, int(duration - current_focus))
        progress = min(1.0, current_focus / duration) if duration else 1.0
    elif phase == "break":
        elapsed = _seconds_between(timer["phase_started_at"], current)
        total_break += elapsed
        current_break += elapsed
        duration = int(timer["break_minutes"]) * 60
        remaining = max(0, int(duration - current_break))
        progress = min(1.0, current_break / duration) if duration else 1.0
    else:
        duration = int(timer["pomodoro_minutes"]) * 60
        remaining = max(0, int(duration - current_focus))
        progress = min(1.0, current_focus / duration) if duration else 1.0

    return {
        "active": True,
        "phase": phase,
        "focus_minutes": round(total_focus / 60, 2),
        "break_elapsed_minutes": round(total_break / 60, 2),
        "remaining_seconds": remaining,
        "progress": progress,
        "completed_pomodoros": int(timer["completed_pomodoros"]),
        "target_pomodoros": int(timer["target_pomodoros"]),
        "subject": timer["subject"],
        "book_or_course": timer["book_or_course"],
        "chapter": timer["chapter"],
    }


def format_seconds(total_seconds: int) -> str:
    minutes, seconds = divmod(max(0, int(total_seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def pending_pomodoro_events() -> list[dict[str, Any]]:
    return list(get_timer().get("pending_pomodoro_events", []))


def mark_pomodoro_event_saved(event_id: str) -> None:
    timer = get_timer()
    timer["pending_pomodoro_events"] = [
        event for event in timer.get("pending_pomodoro_events", []) if event.get("id") != event_id
    ]


def pending_session_record() -> dict[str, Any] | None:
    record = get_timer().get("pending_session_record")
    return dict(record) if record else None


def mark_session_record_saved() -> None:
    timer = get_timer()
    timer["pending_session_record"] = None
