from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st


DEFAULT_TIMEZONE = "Asia/Taipei"


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppConfig:
    app_passcode: str | None
    google_sheet_id: str | None
    google_credentials: dict[str, Any] | None
    timezone: str = DEFAULT_TIMEZONE

    @property
    def credentials_json(self) -> str:
        if not self.google_credentials:
            return ""
        return json.dumps(self.google_credentials, sort_keys=True)


def _streamlit_secret(key: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _secret_section(key: str) -> dict[str, Any] | None:
    try:
        value = st.secrets[key]
    except Exception:
        return None
    return _to_plain_dict(value)


def _to_plain_dict(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _to_plain_dict(v) for k, v in value.items()}
    if hasattr(value, "to_dict"):
        return _to_plain_dict(value.to_dict())
    if isinstance(value, list):
        return [_to_plain_dict(item) for item in value]
    return value


def _normalize_private_key(credentials: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(credentials)
    private_key = normalized.get("private_key")
    if isinstance(private_key, str):
        normalized["private_key"] = private_key.replace("\\n", "\n")
    return normalized


def _load_credentials_from_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return _normalize_private_key(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise ConfigError("GOOGLE_SERVICE_ACCOUNT_JSON 不是有效的 JSON。") from exc


def _load_credentials_from_file(path_value: str | None) -> dict[str, Any] | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser()
    if not path.exists():
        raise ConfigError(f"GOOGLE_APPLICATION_CREDENTIALS 檔案不存在：{path}")
    try:
        return _normalize_private_key(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Google credentials 檔案不是有效 JSON：{path}") from exc


def load_config() -> AppConfig:
    app_passcode = (
        _streamlit_secret("APP_PASSCODE")
        or _streamlit_secret("app_passcode")
        or os.getenv("APP_PASSCODE")
        or os.getenv("STUDY_APP_PASSCODE")
    )

    google_sheet_id = (
        _streamlit_secret("GOOGLE_SHEET_ID")
        or _streamlit_secret("google_sheet_id")
        or os.getenv("GOOGLE_SHEET_ID")
    )

    credentials = (
        _load_credentials_from_json(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
        or _load_credentials_from_json(_streamlit_secret("GOOGLE_SERVICE_ACCOUNT_JSON"))
        or _secret_section("google_service_account")
        or _secret_section("gcp_service_account")
        or _load_credentials_from_file(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    )
    if credentials:
        credentials = _normalize_private_key(credentials)

    timezone = (
        _streamlit_secret("APP_TIMEZONE")
        or _streamlit_secret("app_timezone")
        or os.getenv("APP_TIMEZONE")
        or DEFAULT_TIMEZONE
    )

    return AppConfig(
        app_passcode=str(app_passcode) if app_passcode else None,
        google_sheet_id=str(google_sheet_id) if google_sheet_id else None,
        google_credentials=credentials,
        timezone=str(timezone),
    )


def validate_runtime_config(config: AppConfig) -> None:
    missing = []
    if not config.app_passcode:
        missing.append("APP_PASSCODE")
    if not config.google_sheet_id:
        missing.append("GOOGLE_SHEET_ID")
    if not config.google_credentials:
        missing.append("google_service_account 或 GOOGLE_SERVICE_ACCOUNT_JSON")
    if missing:
        raise ConfigError("缺少設定：" + ", ".join(missing))

    placeholder_fields = []
    if _looks_like_placeholder(config.app_passcode):
        placeholder_fields.append("APP_PASSCODE")
    if _looks_like_placeholder(config.google_sheet_id):
        placeholder_fields.append("GOOGLE_SHEET_ID")
    for key, value in (config.google_credentials or {}).items():
        if _looks_like_placeholder(value):
            placeholder_fields.append(f"google_service_account.{key}")

    if placeholder_fields:
        raise ConfigError("secrets.toml 仍有 placeholder，請替換：" + ", ".join(placeholder_fields))


def _looks_like_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    markers = ["CHANGE_ME", "your-", "your_", "..."]
    return any(marker in value for marker in markers)
