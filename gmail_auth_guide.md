# Gmail OAuth 認證機制說明

## 架構總覽

```
Google Cloud Console
    ↓ 下載
credentials.json
    ↓ 首次授權 (get_gmail_token.py)
token.json
    ↓ 複製 JSON 內容
HF Secret: GMAIL_CREDENTIALS
    ↓ App 運行時讀取
get_gmail_service() → 用 refresh_token 換新 access_token → 呼叫 Gmail API 寄信
```

## 各元件說明

| 檔案/變數 | 用途 | 壽命 |
|---|---|---|
| `credentials.json` | GCP OAuth Client 憑證（client_id + client_secret），用於發起授權流程 | 永久（除非在 GCP 刪除或重設） |
| `token.json` | 本地儲存的 OAuth token（含 access_token + refresh_token） | 見下方說明 |
| `GMAIL_CREDENTIALS`（HF Secret） | `token.json` 的 JSON 內容，供雲端環境使用 | 與 token.json 相同，是靜態快照 |
| Access Token | 實際呼叫 Gmail API 的短期憑證 | **約 1 小時** |
| Refresh Token | 用來換發新 access token 的長期憑證 | 見下方「過期條件」 |

## Token 生命週期

### 首次設定流程

1. 使用者執行 `python get_gmail_token.py`
2. 腳本開啟瀏覽器，導向 Google OAuth 授權頁面
3. 使用者同意授權後，Google 回傳 access_token + refresh_token
4. 腳本寫入 `token.json`
5. 腳本顯示 JSON 內容，供使用者貼到 HF Secret `GMAIL_CREDENTIALS`

### 每次寄信流程

1. App 讀取 `GMAIL_CREDENTIALS`（雲端）或 `token.json`（本地）
2. App 用 refresh_token 向 Google 請求新的 access_token
3. Google 回傳新 access_token（有效約 1 小時）
4. App 用新 access_token 呼叫 Gmail API 寄信

## Access Token vs Refresh Token

| | Access Token | Refresh Token |
|---|---|---|
| 用途 | 直接呼叫 Gmail API | 換發新的 access token |
| 壽命 | ~1 小時 | 長期（條件式過期） |
| 儲存位置 | token.json / GMAIL_CREDENTIALS / 記憶體 | token.json / GMAIL_CREDENTIALS |
| 過期後果 | 程式自動用 refresh_token 換新的 | **必須重新人工授權** |

## GMAIL_CREDENTIALS 的本質

`GMAIL_CREDENTIALS` 是 Hugging Face Secrets 中的環境變數，內容就是 `token.json` 的 JSON **靜態快照**：

```json
{
  "token": "ya29.xxx...",          ← access_token（已過期也沒關係）
  "refresh_token": "1//0exxx...",  ← 這才是關鍵
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "190770877790-xxx.apps.googleusercontent.com",
  "client_secret": "GOCSPX-xxx",
  "scopes": ["https://www.googleapis.com/auth/gmail.send"]
}
```

**重點**：即使裡面的 access_token 早已過期，只要 refresh_token 仍有效，程式就能正常運作。程式每次啟動都會用 refresh_token 即時換一個新的 access_token（在記憶體中），不需要更新 HF Secret。

## Refresh Token 過期條件

| GCP OAuth Consent Screen 狀態 | Refresh Token 壽命 |
|---|---|
| **Testing（測試中）** | **7 天** |
| Production + External（已發布） | 6 個月未使用才過期 |
| Production + Internal（Workspace） | 永不過期 |

其他失效情況（不論狀態）：
- 使用者在 Google 帳號設定中撤銷授權
- 使用者更改 Google 密碼
- 同一帳號累計超過 50 個 refresh token（最舊的會被撤銷）
- GCP 專案中刪除了 OAuth Client

## 程式碼中的刷新邏輯

位於 `wordApp_web.py` 的 `get_gmail_service()`：

```python
# 1. 讀取憑證（優先 env，其次 token.json）
creds_json = os.environ.get("GMAIL_CREDENTIALS")

# 2. 無條件刷新（不信任 expired flag）
if creds.refresh_token:
    creds.refresh(Request())  # 用 refresh_token 換新 access_token

# 3. 本地環境才回寫 token.json（雲端不回寫）
if not IS_CLOUD and os.path.exists('token.json'):
    with open('token.json', 'w') as token_file:
        token_file.write(creds.to_json())
```

## 維護建議

1. **將 GCP 專案發布為 Production** → refresh_token 長期有效
2. **App 持續有在寄信**（至少每 6 個月一次）→ refresh_token 不會因閒置過期
3. **若收到寄信失敗通知**：
   - 本地重跑 `python get_gmail_token.py`
   - 將新的 JSON 更新到 HF Secret `GMAIL_CREDENTIALS`
4. **不需要定期更新 GMAIL_CREDENTIALS**，只要 refresh_token 有效就可以一直用
