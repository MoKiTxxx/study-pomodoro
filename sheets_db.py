from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1


STUDY_SESSIONS_WORKSHEET = "study_sessions"
POMODORO_EVENTS_WORKSHEET = "pomodoro_events"

STUDY_SESSION_HEADERS = [
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

POMODORO_EVENT_HEADERS = [
    "id",
    "session_id",
    "date",
    "start_time",
    "end_time",
    "focus_minutes",
    "status",
    "created_at",
]


class SheetsDB:
    def __init__(self, sheet_id: str, credentials_info: dict[str, Any]):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(credentials_info, scopes=scopes)
        self.client = gspread.authorize(credentials)
        self.spreadsheet = self.client.open_by_key(sheet_id)
        self.study_ws = self._get_or_create_worksheet(
            STUDY_SESSIONS_WORKSHEET,
            STUDY_SESSION_HEADERS,
        )
        self.events_ws = self._get_or_create_worksheet(
            POMODORO_EVENTS_WORKSHEET,
            POMODORO_EVENT_HEADERS,
        )

    def _get_or_create_worksheet(self, title: str, headers: list[str]):
        try:
            worksheet = self.spreadsheet.worksheet(title)
        except WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=title,
                rows=1000,
                cols=max(20, len(headers)),
            )
        self._ensure_header(worksheet, headers)
        return worksheet

    def _ensure_header(self, worksheet, expected_headers: list[str]) -> list[str]:
        header = worksheet.row_values(1)
        if not any(header):
            worksheet.update(values=[expected_headers], range_name="A1")
            return list(expected_headers)

        normalized = [item.strip() for item in header]
        missing = [column for column in expected_headers if column not in normalized]
        if missing:
            normalized.extend(missing)
            worksheet.update(values=[normalized], range_name="A1")
        return normalized

    def _records_df(self, worksheet, expected_headers: list[str]) -> pd.DataFrame:
        self._ensure_header(worksheet, expected_headers)
        records = worksheet.get_all_records()
        if not records:
            return pd.DataFrame(columns=expected_headers)
        df = pd.DataFrame(records)
        for column in expected_headers:
            if column not in df.columns:
                df[column] = ""
        return df[expected_headers]

    def get_study_sessions_df(self) -> pd.DataFrame:
        return self._records_df(self.study_ws, STUDY_SESSION_HEADERS)

    def get_pomodoro_events_df(self) -> pd.DataFrame:
        return self._records_df(self.events_ws, POMODORO_EVENT_HEADERS)

    def upsert_study_session(self, record: dict[str, Any]) -> None:
        self._upsert_record(self.study_ws, STUDY_SESSION_HEADERS, record)

    def upsert_pomodoro_event(self, record: dict[str, Any]) -> None:
        self._upsert_record(self.events_ws, POMODORO_EVENT_HEADERS, record)

    def update_session_fields(
        self,
        session_id: str,
        fields: dict[str, Any],
        timezone: str = "Asia/Taipei",
    ) -> None:
        if not session_id:
            return

        header = self._ensure_header(self.study_ws, STUDY_SESSION_HEADERS)
        row_number = self._find_row_by_id(self.study_ws, header, session_id)
        if not row_number:
            raise KeyError(f"找不到 session id：{session_id}")

        fields = dict(fields)
        fields["updated_at"] = datetime.now(ZoneInfo(timezone)).isoformat()
        updates = []
        for field, value in fields.items():
            if field not in header:
                header.append(field)
                self.study_ws.update(values=[header], range_name="A1")
            col_number = header.index(field) + 1
            updates.append(
                {
                    "range": rowcol_to_a1(row_number, col_number),
                    "values": [[value]],
                }
            )
        if updates:
            self.study_ws.batch_update(updates)

    def _upsert_record(self, worksheet, expected_headers: list[str], record: dict[str, Any]) -> None:
        header = self._ensure_header(worksheet, expected_headers)
        values = [record.get(column, "") for column in header]
        row_number = self._find_row_by_id(worksheet, header, str(record.get("id", "")))

        if row_number:
            last_col = rowcol_to_a1(row_number, len(header))
            worksheet.update(values=[values], range_name=f"A{row_number}:{last_col}")
        else:
            worksheet.append_row(values, value_input_option="USER_ENTERED")

    def _find_row_by_id(self, worksheet, header: list[str], record_id: str) -> int | None:
        if not record_id or "id" not in header:
            return None
        id_col = header.index("id") + 1
        ids = worksheet.col_values(id_col)
        for row_number, value in enumerate(ids[1:], start=2):
            if str(value) == str(record_id):
                return row_number
        return None
