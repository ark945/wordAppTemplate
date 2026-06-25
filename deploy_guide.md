# 複習進度表系統 (模板版) 從無到有佈署指南

這份指南將引導您如何**從零開始**在 Supabase 建立新的資料庫實例 (Instance)，並在 Hugging Face (HF) Spaces 上建立獨立且可自訂網址的系統。

---

## 🛠️ 第一階段：Supabase 資料庫初始化 (全新實例)

如果您想與現行版本完全分離，請在 Supabase 建立一個全新的 Project：

### 1. 建立新專案
1. 登入 [Supabase Dashboard](https://supabase.com/dashboard/)。
2. 點擊 **"New Project"**，選擇您的 Organization，並填寫專案名稱 (例如：`WordApp-Basic`)、設定資料庫密碼與區域。
3. 建立後，請稍等 1-2 分鐘讓資料庫實例配置完畢。
Database password：YOUR_DATABASE_PASSWORD

### 2. 執行 SQL 結構初始化
1. 在左側選單點擊 **"SQL Editor"**。
2. 點擊 **"New query"** (新建查詢)。
3. 複製並貼上專案根目錄下的 [`supabase_init.sql`](supabase_init.sql) 完整內容，然後點擊 **"Run"**。
4. 看到 **"Success"** 即代表以下四個資料表與 RLS 政策已成功建立：
   * `words`：儲存單元單字。
   * `users`：儲存學生名單。
   * `quiz_results`：儲存學生測驗分數與正確率。
   * `system_config`：儲存後台配置（複習起迄日期、規定天數、信箱設定等）。

### 3. 建立儲存空間 (Bucket) 用以存放單字 PDF
1. 點擊左側選單的 **"Storage"**。
2. 點擊 **"New Bucket"**。
3. **Bucket Name** 欄位輸入：`pdfs` (務必全小寫)。
4. 開啟 **"Public bucket"** 選項（此選項方便前台取得 PDF 資料）。
5. 點擊 **"Save"**。

---

## 🚀 第二階段：Hugging Face Spaces 建立與自訂網址

Hugging Face Spaces 提供免費的 Docker 託管服務，您可以自由命名您的 Space 來獲得自訂的網址。

### 0. (選擇性) 建立組織以獲得自訂網址前綴 (避免使用個人帳號名稱)
如果您不希望網址開頭顯示您的個人 Hugging Face 帳號名稱 (例如 `ark945`)，可以免費建立一個組織：
1. 點選 Hugging Face 右上角頭像，選擇 **"New Organization"**。
2. **Organization Username**：填入您想要的網址前綴（例如：`easy-english`）。
3. 建立後，您就可以在下一步建立 Space 時，將擁有者 (Owner) 設為該組織，網址將會自動變為：`https://easy-english-Space名稱.hf.space`。

### 1. 建立新 Space
1. 前往 [Hugging Face Spaces](https://huggingface.co/spaces) 頁面。
2. 點擊右上角的 **"Create new Space"**。
3. **Owner (擁有者)**：
   * 預設為您的個人帳號。如果您在「步驟 0」建立了組織，請在下拉選單中**切換成該組織**。
4. **Space name (重要 - 自訂網址名稱)**：
   * 這會決定您的最終網址。例如：若 Owner 為 `easy-english` 且名稱輸入 `word-app`，您的網址將會是：
     `https://huggingface.co/spaces/easy-english/word-app`
     其獨立全螢幕網址將會是：
     `https://easy-english-word-app.hf.space/`
     MyClass
5. **License**：留空或輸入 `mit`。
6. **SDK**：務必選擇 **"Docker"**。
7. **Template**：選擇 **"Blank"**。
8. **Space hardware**：選擇預設的 **"Cpu basic • 2 vCPU • 16 GB • Free"**。
9. **Visibility**：選擇 **"Public"** (若需要隱私保護，本專案已自帶後台密碼鎖，所以 Public 即可)。
10. 點擊底部的 **"Create Space"**。

### 2. 在 Hugging Face 設定環境變數 (Secrets)
1. 進入您剛建立 the Space 頁面，點擊上方的 **"Settings"** 頁籤。
2. 在左側選單點選 **"Variables and secrets"**。
3. 點選 **"New secret"** 依次新增以下環境變數：

| Secret Key (名字) | Value (填寫內容) | 說明 |
| :--- | :--- | :--- |
| `SUPABASE_URL` | 您的新 Supabase API 網址 | 於左側選單 **INTEGRATIONS -> Data API** 最上方的 `API URL` 取得（只需複製到 `.supabase.co` 即可，例如：`https://xxxx.supabase.co`） |
https://YOUR_SUPABASE_PROJECT_ID.supabase.co
| `SUPABASE_KEY` | 您的新 Supabase `service_role` 金鑰 | 於左側選單 **Project Settings (齒輪) -> API Keys -> Secret keys** 下的 **default**（點擊 Reveal 顯示後複製以 `sb_secret_` 開頭的金鑰） |
YOUR_SUPABASE_SERVICE_ROLE_KEY
| `ADMIN_USERNAME` | 您的自訂後台登入帳號 | 例如：`teacher` (若不設定，預設為 `admin`) |
| `ADMIN_PASSWORD` | 您的自訂後台登入密碼 | 例如：`mysecurepwd123` (若不設定，預設為 `admin123`) |

---

## 💻 第三階段：Git 本地推送與佈署

請在您的本機電腦上，開啟終端機（PowerShell 或 Command Prompt）將模板專案推送至新建立的 HF Space。

### 1. 初始化本地 Git 倉庫並進行首次提交
如果您尚未在此資料夾進行 git 初始化，請執行：
```bash
# 1. 進入您的模板專案目錄
cd d:\MyLab\wordAppTemplate

# 2. 初始化 Git 倉庫
git init

# 3. 將所有修改與檔案加入暫存區
git add .

# 4. 進行本地 Commit 提交
git commit -m "feat: init review progress template with admin panel"
```

### 2. 連接 Hugging Face 並推送
1. 在您建立的 Hugging Face Space 頁面中，點擊右上角 **"Use via Git"** 或 **"Clone this Space"** 可看見專屬的 git 位址。
2. 在終端機執行以下指令連接並強制推送：
```bash
# 連接您的新 Space（請將下方的用戶名與 Space 名稱替換為您實際的內容）
git remote add hf https://huggingface.co/spaces/您的HF帳號/您的Space名稱

# 推送代碼至 Hugging Face (通常預設分支為 main)
git push -f hf main
```
3. 推送後，HF 網頁上的 App 狀態會轉為 **"Building"**，編譯約需 2-3 分鐘。
4. 狀態變為綠色的 **"Running"** 時，即代表網頁建置完成！您可以點擊網址進入系統。

---

## ⚙️ 第四階段：後台設定與使用指引 (免動代碼)

網頁成功執行後，您不需要修改任何程式碼，只要在瀏覽器上操作後台即可：

### 1. 登入後台
1. 打開您的網頁（例如 `https://您的帳號-Space名稱.hf.space/`）。
2. 點選右上角的 **"🔐 後台管理"** 按鈕。
3. 輸入您在 HF Secrets 中設定的 `ADMIN_USERNAME` 與 `ADMIN_PASSWORD`。

### 2. 進行首次設定
在後台主控台中，您可以設定以下三大項目，儲存後會立即寫入 Supabase 中：
1. **複習進度表設定**：
   * **複習起迄時間**：選擇本次進度表的開始與結束日期。
   * **規定複習次數**：設定學生需要達到幾天 (例如 1 天或 2 天)。
   * **複習單元列表**：系統會自動抓取您匯入的單字單元，點選 **"全選"** 或 **"全不選"**，並勾選本次要納入計分的單元。（*注意：未勾選的單元不會出現在進度表上*）。
2. **郵件通知設定 (SMTP 簡單設定)**：
   * 勾選 **"啟用測驗完成 Email 通知"**。
   * 輸入 **"寄件者信箱"** (例如您的 Gmail 地址)。
   * 輸入 **"郵件授權密碼 (App Password)"**（至 Google 帳號安全性設定中產生 16 位元應用程式密碼）。
   * 輸入 **"收件者信箱"**（多位家長/老師請用逗號隔開）。
3. **儲存設定**：
   * 點選 **"💾 儲存所有設定"**，即刻完成部署！
