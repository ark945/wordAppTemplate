# wordAppOnWeb 現代化轉型方案總結

這份文件總結了將您的單字 App 從「本地開發版」轉型為「雲端穩定版」的最佳做法。

## 1. 雲端網站 (Website Hosting)
*   **推薦平台**：**Hugging Face Spaces** (或 Render)。
*   **做法**：將程式碼打包成 Docker 容器佈署。
*   **優勢**：
    *   Hugging Face 提供免費 16GB RAM，資源多。
    *   休眠時間長 (48小時)，不像 Render 15分鐘就關機，發信背景作業更穩定。

## 2. 雲端資料庫 (Database & Storage)
*   **服務商**：**Supabase**。
*   **資料庫 (DB)**：使用 Supabase PostgreSQL。
    *   **改善點**：取代原本的 SQLite `vocab.db`。資料永久儲存，重啟伺服器不會消失。
*   **檔案儲存 (Storage)**：使用 Supabase Storage (Bucket 名稱為 `pdfs`)。
    *   **改善點**：取代 GitHub 或本地資料夾。PDF 統一存在雲端，並有專屬網址。

## 3. 寄送 Email (Gmail SMTP)
*   **服務商**：**Gmail**。
*   **必要設定**：**Google 應用程式密碼 (App Password)**。
    *   您必須開啟 Google 帳號的「兩階段驗證」，然後生成一個 16 位元的「應用程式密碼」供程式連線使用。
*   **實作改進**：
    *   使用 `threading` 背景發信。
    *   加入更強的錯誤捕捉運算 (Retry Logic)，解決雲端 IP 偶爾連不上 Gmail 的問題。

## 4. 設定檔與安全 (Configuration)
*   **做法**：**環境變數 (Environment Variables)**。
*   **說明**：為了安全，我們**不會**把秘密金鑰寫在 `wordApp_web.py` 裡面。
*   **需要存放的變數**：
    *   `SUPABASE_URL`: (您已取得)
    *   `SUPABASE_KEY`: (您已取得，即 Secret Key)
    *   `GMAIL_USER`: 您的 Gmail 地址。
    *   `GMAIL_PASSWORD`: 您的 16 位元應用程式密碼。
    *   `RECEIVERS`: 收件人清單。

## ⚙️ 接下來的開發順序
1.  **[變更資料庫層]**：把 `DatabaseManager` 從 SQL 語法改為 Supabase SDK 呼叫。
2.  **[接入儲存空間]**：改寫上傳邏輯，將 PDF 推送到 Supabase Storage。
3.  **[改進郵件邏輯]**：封裝一個標準的發信類別，支援 Gmail 的穩定連線。
4.  **[產生佈署檔案]**：撰寫 `Dockerfile` 與 `requirements.txt`。

---

> [!TIP]
> **為什麼不去買網域？**
> 因為您的需求是「穩定且免費且發給別人」。在沒有網域的情況下，用 Gmail SMTP 配合「應用程式密碼」雖然稍微傳統，但對於非商業、輕量級的小工具來說，這依然是最具成本效益且能寄信給任何人的方式。
