# 使用 Python 3.9 作為基礎鏡像
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 複製依賴文件並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt



# 複製專案原始碼
COPY . .

# 暴露 Flask 預設端口 (Hugging Face Spaces 要求 7860)
EXPOSE 7860

# 使用 Gunicorn 啟動應用程式 (適合雲端生產環境)
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--timeout", "300", "wordApp_web:app"]
