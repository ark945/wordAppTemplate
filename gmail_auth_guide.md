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

## 兩個 Google 帳號的角色說明

本專案涉及兩個不同的 Google 帳號，各自負責不同的事：

### 帳號角色對照表

| | ark221（專案擁有者） | arkdd1（寄信帳號） |
|---|---|---|
| 做了什麼 | 建立 GCP 專案、申請 OAuth Client | 授權 App 使用自己的 Gmail 寄信 |
| 何時需要 | 只有最初設定時 | 只有授權時（跑 get_gmail_token.py） |
| 日常運作需要嗎 | ❌ 不需要 | ❌ 不需要 |
| 產生的檔案 | `credentials.json` | `token.json` |
| 收件者看到的 | 看不到 ark221 | 看到寄件者是 arkdd1@gmail.com |

### 完整流程圖（誰在什麼時候做了什麼）

```
═══════════════════════════════════════════════════════════════
  步驟 1：建立 App（一次性，由 ark221 完成）
═══════════════════════════════════════════════════════════════

  ark221 登入 GCP Console
      ↓
  建立專案 "word-app-mail"
      ↓
  啟用 Gmail API
      ↓
  建立 OAuth 2.0 Client ID（桌面應用程式）
      ↓
  下載 → credentials.json（內含 client_id + client_secret）

  ✅ ark221 的工作到此結束，之後不再需要 ark221

═══════════════════════════════════════════════════════════════
  步驟 2：授權寄信（一次性，由 arkdd1 完成）
═══════════════════════════════════════════════════════════════

  執行 python get_gmail_token.py
      ↓
  瀏覽器開啟 Google 登入頁面
      ↓
  arkdd1@gmail.com 登入
      ↓
  Google 顯示：「word-app-mail 想要存取你的 Gmail，是否允許？」
      ↓
  arkdd1 點「允許」
      ↓
  Google 發放 refresh_token 給這個 App
      ↓
  寫入 → token.json（內含 refresh_token）

  ✅ arkdd1 的工作到此結束，之後不再需要手動操作

═══════════════════════════════════════════════════════════════
  步驟 3：日常寄信（全自動，不需要任何人介入）
═══════════════════════════════════════════════════════════════

  App (wordApp_web.py) 啟動
      ↓
  讀取 credentials.json 的 client_id/client_secret（App 的身份證）
  讀取 token.json 的 refresh_token（arkdd1 給的授權）
      ↓
  向 Google 說：「我是 word-app-mail App，arkdd1 授權我寄信，給我新的 access_token」
      ↓
  Google 驗證通過，發放 access_token
      ↓
  App 用 access_token 呼叫 Gmail API
      ↓
  信件從 arkdd1@gmail.com 寄出 ✉️

  （ark221 完全不參與這個過程）
```

### 為什麼需要兩個帳號？

其實**不一定需要兩個帳號**。同一個人可以用同一個 Google 帳號同時：
- 建立 GCP 專案（開發者角色）
- 授權寄信（使用者角色）

本專案剛好是用不同帳號做這兩件事。可能是當初設定時用了不同帳號登入。

### 類比說明

想像一個「自動寄信機器人」：

- **ark221** = 去政府（Google）登記了一家公司（GCP 專案），拿到營業執照（credentials.json）
- **arkdd1** = 把自己的 Gmail 信箱鑰匙（refresh_token）交給這家公司，說「你可以代替我寄信」
- **App** = 這家公司的員工，每天拿著營業執照和鑰匙去郵局（Gmail API）寄信

收件者只會看到信是 arkdd1 寄的，不會知道 ark221 或這家公司的存在。

### 如果 token 失效了怎麼辦？

只需要 **arkdd1** 重新授權：

```bash
python get_gmail_token.py
# arkdd1 在瀏覽器重新點「允許」
# 更新 HF Secret GMAIL_CREDENTIALS
```

**不需要** ark221 做任何事（除非 GCP 專案本身被刪除）。

## 維護建議

1. **將 GCP 專案發布為 Production**（需用 ark221 登入 GCP Console）→ refresh_token 長期有效
2. **App 持續有在寄信**（至少每 6 個月一次）→ refresh_token 不會因閒置過期
3. **若收到寄信失敗通知**：
   - 本地重跑 `python get_gmail_token.py`（用 arkdd1 帳號授權）
   - 將新的 JSON 更新到 HF Secret `GMAIL_CREDENTIALS`
4. **不需要定期更新 GMAIL_CREDENTIALS**，只要 refresh_token 有效就可以一直用
