# 讀書番茄鐘紀錄系統

這是一個用 **Python + Streamlit** 做的讀書番茄鐘網頁系統。它可以記錄每次讀書工作階段，把資料寫入 **Google Sheets**，並用 **pandas** 與 **matplotlib** 做今日紀錄、累積統計、搜尋和 CSV 匯出。

專案已設計成可以上傳到 GitHub，並部署到 Streamlit Community Cloud。機密資料不寫在程式碼中，改由 Streamlit Secrets 或環境變數提供。

## 專案在做什麼

這個系統的目標是幫你把「讀書時間」轉成可以追蹤、回顧、統計的資料。

你可以在開始讀書前填入：

- 任務類型
- 科目
- 書本或課程
- 章節
- 開始前備註
- 計時模式與休息安排

讀書時系統會：

- 倒數每段專注時間
- 自動安排休息時間
- 暫停時不計入專注時間
- 休息時間不計入讀書時間
- 每段專注結束時播放 `Alarm.mp3`
- 完成後寫入 Google Sheets

之後你可以查看：

- 今日總專注時間
- 今日番茄鐘數
- 今日各科時數
- 累積總時數
- 每週統計
- 最近 7 日與 30 日平均
- 每日讀書時數折線圖
- 搜尋歷史紀錄
- 匯出 CSV

## 主要功能

- Passcode 登入保護
- 中文 / 英文 UI
- 手動分段模式
- 自動模式：輸入總時間、分段數、總休息時間，自動換算每段專注與休息時間
- Start / Pause / Resume / Stop work
- 完成番茄鐘後自動寫入 Google Sheets
- Google Sheets worksheet 和表頭不存在時自動建立
- 空資料表不報錯
- 今日紀錄可補填：
  - output
  - stuck
  - next_action
- 累積統計全部從 Google Sheets 重新計算，不手動儲存累積值
- CSV 匯出：
  - 全部紀錄
  - 今日紀錄
  - 每週摘要
  - 各科統計

## 技術

- Python
- Streamlit
- Google Sheets API
- gspread
- pandas
- matplotlib
- streamlit-autorefresh

## 專案檔案

```text
app.py
auth.py
config.py
sheets_db.py
timer_state.py
analytics.py
export.py
requirements.txt
runtime.txt
DEPLOY.md
README.md
.gitignore
.streamlit/secrets.toml.example
Alarm.mp3
```

## Google Sheets 資料表

系統會使用兩個 worksheet：

```text
study_sessions
pomodoro_events
```

### study_sessions 欄位

```text
id, date, start_time, end_time, subject, book_or_course, chapter, task_type, proof_status, plan_note, focus_minutes, break_minutes, completed_pomodoros, pomodoro_minutes, status, output, stuck, next_action, created_at, updated_at
```

### pomodoro_events 欄位

```text
id, session_id, date, start_time, end_time, focus_minutes, status, created_at
```

統計主要計入 `completed`。舊版本保留的 `saved_partial` 資料也會被統計，以維持相容性。`stopped` 不計入統計。

## 安裝

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 建立 Google Sheet

1. 到 Google Sheets 建立一份新的試算表。
2. 從網址取得 Sheet ID。

網址格式通常像這樣：

```text
https://docs.google.com/spreadsheets/d/<GOOGLE_SHEET_ID>/edit
```

`<GOOGLE_SHEET_ID>` 就是要放進 secrets 的值。

你不需要手動建立 `study_sessions` 和 `pomodoro_events`，程式會自動建立。

## 建立 Google Service Account

1. 到 Google Cloud Console。
2. 建立或選擇一個 project。
3. 啟用 Google Sheets API。
4. 啟用 Google Drive API。
5. 進入 IAM & Admin > Service Accounts。
6. 建立 service account。
7. 到該 service account 的 Keys 頁面。
8. 新增 JSON key 並下載。

下載的 JSON key 不要上傳 GitHub。

## 分享 Google Sheet

1. 打開你的 Google Sheet。
2. 點右上角「共用」。
3. 從 service account JSON 裡找到 `client_email`。
4. 把這個 email 加入 Sheet 共用名單。
5. 權限設成 Editor / 編輯者。

## 設定 Secrets

本機建立：

```powershell
mkdir .streamlit
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

`.streamlit/secrets.toml` 範例：

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

真正的 `.streamlit/secrets.toml` 不要 commit。

## 本機執行

```powershell
streamlit run app.py
```

瀏覽器會開啟：

```text
http://localhost:8501
```

輸入 `APP_PASSCODE` 後即可使用。

## 部署到 Streamlit Community Cloud

1. 把專案 push 到 GitHub。
2. 到 Streamlit Community Cloud 建立 app。
3. Repository 選這個專案。
4. Branch 選 `main`。
5. Main file path 填：

```text
app.py
```

6. Advanced settings 裡的 Secrets 貼上 `.streamlit/secrets.toml` 的內容。
7. Deploy。

注意：Streamlit Cloud 的 Secrets 欄位要貼 TOML 內容，不是貼 `.streamlit/secrets.toml` 這個路徑。

## 安全注意事項

`.gitignore` 會排除：

```text
.env
.streamlit/secrets.toml
*.json
__pycache__/
*.pyc
.venv/
venv/
*.csv
exports/
*.db
*.sqlite
*.sqlite3
```

不要把以下檔案上傳到 GitHub：

- `.streamlit/secrets.toml`
- Google service account JSON key
- `.env`

## 線上版本

目前部署網址：

```text
https://study-pomodoro-c6fojvylxscymcgpvbqogz.streamlit.app/
```
