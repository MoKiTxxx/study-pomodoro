# 網頁部署最快流程

這個專案可以部署到 Streamlit Community Cloud，部署後就是一個可用的網頁 App。

## 1. 先準備 Google Sheet

1. 建立一個新的 Google Sheet。
2. 從網址複製 Sheet ID：

```text
https://docs.google.com/spreadsheets/d/這一段就是_GOOGLE_SHEET_ID/edit
```

3. 建立 Google service account，下載 JSON key。
4. 把 Google Sheet 分享給 JSON 裡的 `client_email`，權限選「編輯者」。

程式會自動建立 `study_sessions` 和 `pomodoro_events` 兩個 worksheet。

## 2. 上傳 GitHub

```bash
git init
git add .
git commit -m "Initial study pomodoro tracker"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

不要把 `.streamlit/secrets.toml` 上傳。這個檔案已經被 `.gitignore` 排除。

## 3. 部署到 Streamlit Community Cloud

1. 到 https://streamlit.io/cloud
2. 點 New app。
3. 選你的 GitHub repo。
4. Main file path 填：

```text
app.py
```

5. 在 App settings > Secrets 貼上：

```toml
APP_PASSCODE = "你要設定的登入密碼"
GOOGLE_SHEET_ID = "你的 Google Sheet ID"
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

6. Deploy。

部署完成後，Streamlit 會給你一個網址。之後你只要打開那個網址、輸入 passcode，就可以在網頁使用。
