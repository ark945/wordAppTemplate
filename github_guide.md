# 程式碼修改與推送指南

這份文件說明當您修改了任何檔案後，如何將變更推送到 **GitHub** 與 **Hugging Face**。

---

## 快速版（複製貼上即可）

當您改完程式碼，在終端機依序貼入以下指令：

```powershell
cd d:\MyProject\wordApp_web

git add .
git commit -m "簡短描述您改了什麼"
git push origin master
git push hf master:main
```

> 推送到 `hf` 後，Hugging Face Space 會**自動重新建置並部署**。

---

## 詳細說明

### Step 1：查看哪些檔案被修改了

```powershell
git status
```

會列出所有被新增、修改、刪除的檔案，方便您確認。

### Step 2：將變更加入暫存區

```powershell
# 加入所有變更
git add .

# 或只加入特定檔案
git add wordApp_web.py
git add templates/quiz.html
```

### Step 3：建立提交（Commit）

```powershell
git commit -m "描述您的改動內容"
```

**提交訊息範例：**
- `"fix: 修正 Email 發送失敗的問題"`
- `"feat: 新增使用者管理頁面"`
- `"style: 調整首頁排版"`

### Step 4：推送到遠端

```powershell
# 推送到 GitHub（原始碼備份）
git push origin master

# 推送到 Hugging Face（正式部署）
git push hf master:main
```

> **注意**：GitHub 的分支名是 `master`，Hugging Face 的分支名是 `main`，所以推送到 HF 時要寫 `master:main`。

---

## 常見問題

### Q: 推送時要求輸入帳號密碼？
- **GitHub**：使用 Personal Access Token 當作密碼（不是 GitHub 登入密碼）。
- **Hugging Face**：使用 HF Access Token 當作密碼。

### Q: 推送失敗顯示 "rejected"？
代表遠端有您本地沒有的變更，先拉取再推送：
```powershell
git pull origin master --rebase
git push origin master
```

### Q: 不小心 commit 了不該提交的檔案？
```powershell
# 撤銷最近一次 commit（保留檔案變更）
git reset --soft HEAD~1
```

---

## 安全注意事項

- **`.gitignore` 已設定**：`config.json`、`token.json`、`.env` 等敏感檔案會被自動排除，不會被推送。
- **絕對不要**手動移除 `.gitignore` 裡的限制，否則您的秘密金鑰會被公開。
- 若要在其他電腦開發，請參考 `config_sample.json` 手動建立您自己的 `config.json`。