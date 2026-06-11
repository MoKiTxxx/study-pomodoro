# 讀書番茄鐘紀錄系統

Python + Streamlit 製作的讀書番茄鐘紀錄系統，資料儲存在 Google Sheets，並用 pandas 統計、matplotlib 畫圖。專案可上傳 GitHub，也可部署到 Streamlit Community Cloud。

## 可以在網頁使用

可以。這不是只能在本機跑的工具。

推薦部署方式是：

1. 專案上傳 GitHub。
2. 到 Streamlit Community Cloud 建立 App。
3. 在 Streamlit Cloud 的 Secrets 設定 passcode、Google Sheet ID、Google service account JSON。
4. 部署後用 Streamlit Cloud 提供的網址登入使用。

最短部署步驟請看 [DEPLOY.md](DEPLOY.md)。

## 功能

- Passcode 保護
- 開始、暫停、繼續、停止、手動完成、儲存部分讀書紀錄
- 使用 timestamp + `st.session_state` 計時，不使用 `while True`
- Pause 不計入專注時間，Break 不計入讀書時間
- 完成番茄鐘自動寫入 Google Sheets
- 今日紀錄、累積統計、搜尋、CSV 匯出
- worksheet 或表頭不存在時會自動建立
- 統計只計入 `completed` 與 `saved_partial`

## 安裝

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS 或 Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 建立 Google Sheet

1. 到 [Google Sheets](https://sheets.google.com/) 建立一份新的試算表。
2. 從網址取得 Sheet ID。
   - 網址格式通常是 `https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_ID>/edit`
3. 不需要手動建立 worksheet。程式會自動建立：
   - `study_sessions`
   - `pomodoro_events`

`study_sessions` 欄位：

```text
id, date, start_time, end_time, subject, book_or_course, chapter, task_type, proof_status, plan_note, focus_minutes, break_minutes, completed_pomodoros, pomodoro_minutes, status, output, stuck, next_action, created_at, updated_at
```

`pomodoro_events` 欄位：

```text
id, session_id, date, start_time, end_time, focus_minutes, status, created_at
```

## 建立 Google service account

1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立或選擇一個 project。
2. 啟用 Google Sheets API。
3. 啟用 Google Drive API。
4. 進入 IAM & Admin > Service Accounts。
5. 建立 service account。
6. 到該 service account 的 Keys 頁面，新增 JSON key。
7. 下載 JSON key 檔案。

## 分享 Sheet 給 service account

1. 打開剛建立的 Google Sheet。
2. 點右上角「共用」。
3. 將 JSON key 裡的 `client_email` 加入分享對象。
4. 權限設定為「編輯者」。

## 設定 secrets

建立本機 secrets 檔案：

```bash
mkdir .streamlit
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

macOS 或 Linux：

```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

編輯 `.streamlit/secrets.toml`：

```toml
APP_PASSCODE = "your-passcode"
GOOGLE_SHEET_ID = "your-google-sheet-id"
APP_TIMEZONE = "Asia/Taipei"

[google_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project-id.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

也可以用環境變數：

```bash
set APP_PASSCODE=your-passcode
set GOOGLE_SHEET_ID=your-google-sheet-id
set GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```

PowerShell：

```powershell
$env:APP_PASSCODE="your-passcode"
$env:GOOGLE_SHEET_ID="your-google-sheet-id"
$env:GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

## 本地執行

```bash
streamlit run app.py
```

瀏覽器開啟 Streamlit 顯示的網址，輸入 `APP_PASSCODE` 後即可使用。

## 上傳 GitHub

```bash
git init
git add .
git commit -m "Initial study pomodoro tracker"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

`.gitignore` 已排除：

- `.env`
- `.streamlit/secrets.toml`
- `__pycache__/`
- `.venv/`
- `venv/`
- `*.csv`

## 部署到 Streamlit Community Cloud

1. 將專案 push 到 GitHub。
2. 到 [Streamlit Community Cloud](https://streamlit.io/cloud)。
3. 建立 New app。
4. 選擇 GitHub repo、branch 與 `app.py`。
5. 到 App settings > Secrets，貼上 `.streamlit/secrets.toml` 的內容。
6. Deploy。

部署後請確認：

- Google Sheet 已分享給 service account email。
- `GOOGLE_SHEET_ID` 正確。
- `APP_PASSCODE` 已設定。
- service account JSON 的 `private_key` 保留 `\n` 換行。
