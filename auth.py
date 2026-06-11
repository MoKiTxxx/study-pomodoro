from __future__ import annotations

from hmac import compare_digest

import streamlit as st

from config import load_config


def require_passcode() -> None:
    config = load_config()

    if not config.app_passcode:
        st.error("尚未設定 APP_PASSCODE。請先在 Streamlit secrets 或環境變數中設定 passcode。")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("讀書番茄鐘紀錄系統")
    with st.form("passcode_form"):
        passcode = st.text_input("Passcode", type="password")
        submitted = st.form_submit_button("登入")

    if submitted:
        if compare_digest(passcode, config.app_passcode):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Passcode 錯誤。")

    st.stop()
