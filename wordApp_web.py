import os
import sys
import re
import time
import json
import socket
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, jsonify, send_file, Response, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import asyncio
import edge_tts
import pdfplumber
from supabase import create_client, Client

# ==========================================
# 0. Global Config (Local vs Cloud)
# ==========================================
CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

# 偵測是否在 Hugging Face Spaces 執行 (通常會有 SPACE_ID)
IS_CLOUD = os.environ.get("SPACE_ID") is not None
local_cfg = load_config()

# --- Supabase Config ---
if IS_CLOUD:
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
else:
    s_cfg = local_cfg.get("supabase_settings", {})
    SUPABASE_URL = s_cfg.get("url", "")
    SUPABASE_KEY = s_cfg.get("key", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ 警告: 缺少 Supabase 設定資訊！")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

app = Flask(__name__, 
            template_folder=resource_path('templates'),
            static_folder=resource_path('static'))
app.secret_key = 'your_secret_key_here'

# ==========================================
# 1. Database Manager (Supabase Version)
# ==========================================
class DatabaseManager:
    def __init__(self):
        # Tables should be manually created in Supabase Dashboard for best performance,
        # but we'll use the API for data operations.
        pass

    def add_word(self, unit, word, pos, definition, sentence):
        try:
            data = {
                "unit": unit,
                "word": word,
                "pos": pos,
                "definition": definition,
                "sentence": sentence
            }
            # Use upsert based on (unit, word) unique constraint if defined in Supabase
            supabase.table("words").upsert(data, on_conflict="unit,word,pos").execute()
        except Exception as e:
            print(f"Supabase Add Word Error: {e}")

    def clear_all_data(self):
        try:
            # Delete all rows (requires RLS policy or service role key)
            supabase.table("words").delete().neq("id", -1).execute()
            return True
        except Exception as e:
            print(f"Supabase Clear Data Error: {e}")
            return False

    def delete_words_by_unit(self, unit_name):
        try:
            supabase.table("words").delete().eq("unit", unit_name).execute()
            return True
        except Exception as e:
            print(f"Supabase Delete Unit Error: {e}")
            return False

    def rename_unit(self, old_name, new_name):
        try:
            supabase.table("words").update({"unit": new_name}).eq("unit", old_name).execute()
            return True
        except Exception as e:
            print(f"Supabase Rename Unit Error: {e}")
            return False

    def get_units(self):
        try:
            response = supabase.table("words").select("unit").execute()
            units = sorted(list(set([row['unit'] for row in response.data])))
            return units
        except Exception as e:
            print(f"Supabase Get Units Error: {e}")
            return []

    def get_words_by_unit(self, unit_name):
        try:
            response = supabase.table("words").select("*").eq("unit", unit_name).order("id").execute()
            return response.data
        except Exception as e:
            print(f"Supabase Get Words Error: {e}")
            return []

    def get_all_words(self):
        try:
            response = supabase.table("words").select("*").execute()
            return response.data
        except Exception as e:
            print(f"Supabase Get All Words Error: {e}")
            return []

    # --- User APIs ---
    def add_user(self, name):
        try:
            supabase.table("users").insert({"name": name}).execute()
            return True
        except Exception as e:
            print(f"Supabase Add User Error: {e}")
            return False

    def get_users(self):
        try:
            response = supabase.table("users").select("id, name").order("id").execute()
            return response.data
        except Exception as e:
            print(f"Supabase Get Users Error: {e}")
            return []

    def delete_user(self, user_id):
        try:
            supabase.table("users").delete().eq("id", user_id).execute()
        except Exception as e:
            print(f"Supabase Delete User Error: {e}")

    def add_quiz_result(self, user_name, unit, mode, score, total):
        try:
            accuracy = (score / total * 100.0) if total > 0 else 0.0
            data = {
                "user_name": user_name,
                "unit": unit,
                "mode": mode,
                "score": score,
                "total": total,
                "accuracy": accuracy
            }
            supabase.table("quiz_results").insert(data).execute()
            return True
        except Exception as e:
            print(f"Supabase Add Quiz Result Error: {e}")
            return False

    def get_review_progress_records(self, start_date, end_date):
        try:
            # 查詢符合日期區間的測驗結果
            response = supabase.table("quiz_results") \
                .select("*") \
                .gte("created_at", start_date) \
                .lte("created_at", end_date) \
                .execute()
            return response.data
        except Exception as e:
            print(f"Supabase Get Review Progress Error: {e}")
            return []

    def get_config(self, key):
        try:
            res = supabase.table("system_config").select("value").eq("key", key).execute()
            if res.data:
                return res.data[0]["value"]
            return None
        except Exception as e:
            print(f"Supabase Get Config Error: {e}")
            return None

    def set_config(self, key, value):
        try:
            data = {"key": key, "value": value}
            supabase.table("system_config").upsert(data, on_conflict="key").execute()
            return True
        except Exception as e:
            print(f"Supabase Set Config Error: {e}")
            return False

db = DatabaseManager()

# ==========================================
# 1.5. Admin Authentication & Config Helpers
# ==========================================
from functools import wraps

def get_admin_credentials():
    env_user = os.environ.get("ADMIN_USERNAME")
    env_pass = os.environ.get("ADMIN_PASSWORD")
    if env_user and env_pass:
        return env_user, env_pass, True
    
    db_creds = db.get_config("admin_credentials")
    if db_creds:
        return db_creds.get("username", "admin"), db_creds.get("password", "admin123"), False
    
    default_creds = {"username": "admin", "password": "admin123"}
    db.set_config("admin_credentials", default_creds)
    return "admin", "admin123", False

def verify_admin(username, password):
    expected_user, expected_pass, is_env = get_admin_credentials()
    if username != expected_user:
        return False
    if expected_pass.startswith("pbkdf2:"):
        return check_password_hash(expected_pass, password)
    return password == expected_pass

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if verify_admin(username, password):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('login.html', error='帳號或密碼錯誤')
    return render_template('login.html')

@app.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_panel():
    return render_template('admin.html')

@app.route('/api/admin/config', methods=['GET', 'POST'])
@login_required
def api_admin_config():
    if request.method == 'GET':
        r_settings = db.get_config("review_settings")
        if not r_settings:
            r_settings = {
                "start_date": "2026-07-01",
                "end_date": "2026-08-31",
                "required_days": 2,
                "selected_units": []
            }
        e_settings = db.get_config("email_settings")
        if not e_settings:
            e_settings = {
                "sender_email": "",
                "receivers": [],
                "enable": False
            }
        if "app_password" in e_settings:
            del e_settings["app_password"]
            
        config = {
            "review_settings": r_settings,
            "email_settings": e_settings
        }
        available_units = db.get_units()
        return jsonify({
            "success": True,
            "config": config,
            "available_units": available_units
        })
    elif request.method == 'POST':
        data = request.json
        review_settings = data.get("review_settings")
        email_settings = data.get("email_settings")
        if review_settings:
            db.set_config("review_settings", review_settings)
        if email_settings:
            existing_email = db.get_config("email_settings") or {}
            if "app_password" not in email_settings and "app_password" in existing_email:
                email_settings["app_password"] = existing_email["app_password"]
            db.set_config("email_settings", email_settings)
        return jsonify({"success": True})

@app.route('/api/admin/password', methods=['POST'])
@login_required
def api_admin_password():
    data = request.json
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    expected_user, expected_pass, is_env = get_admin_credentials()
    if is_env:
        return jsonify({"success": False, "message": "環境變數中已設定密碼，無法透過網頁修改"})
    if not verify_admin(expected_user, old_password):
        return jsonify({"success": False, "message": "舊密碼不正確"})
    db.set_config("admin_credentials", {
        "username": expected_user,
        "password": new_password
    })
    return jsonify({"success": True})

# ==========================================
# 2. Config & Helpers
# ==========================================
# ==========================================
# 2. Helpers
# ==========================================

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ==========================================
# 3. Routes
# ==========================================

@app.route('/')
def index():
    units = db.get_units()
    return render_template('index.html', units=units)

@app.route('/list/<unit>')
def word_list(unit):
    words = db.get_words_by_unit(unit)
    return render_template('list.html', unit=unit, words=words)

@app.route('/study/<unit>')
def study_mode(unit):
    return render_template('study.html', unit=unit)

@app.route('/quiz/<mode>/<unit>')
def quiz_mode(mode, unit):
    return render_template('quiz.html', mode=mode, unit=unit)

@app.route('/import_page')
def import_page():
    return render_template('import.html')

@app.route('/manage_users')
def manage_users_page():
    return render_template('manage_users.html')

# --- API Endpoints ---

@app.route('/api/words/<unit>')
def api_get_words(unit):
    words = db.get_words_by_unit(unit)
    # Fix sentence spacing
    for w in words:
        if w['sentence']:
            w['sentence'] = w['sentence'].replace('\n', ' ')
    return jsonify(words)

@app.route('/api/all_words')
def api_get_all_words():
    words = db.get_all_words()
    return jsonify(words)

@app.route('/api/tts')
def api_tts():
    text = request.args.get('text', '')
    if not text:
        return "No text provided", 400
    
    # Remove Chinese characters for TTS
    clean_text = text
    if "(" in clean_text: clean_text = clean_text.split("(")[0]
    elif "（" in clean_text: clean_text = clean_text.split("（")[0]
    match = re.search(r'[\u4e00-\u9fff]', clean_text)
    if match: clean_text = clean_text[:match.start()]
    clean_text = clean_text.strip()
    
    try:
        # Use edge-tts (Microsoft neural voice)
        filename = f"tts_{int(time.time()*1000)}.mp3"
        filepath = os.path.join("static", filename)
        
        async def _generate():
            communicate = edge_tts.Communicate(clean_text, voice="en-US-AriaNeural")
            await communicate.save(filepath)
        
        asyncio.run(_generate())
        
        # Cleanup old files
        for f in os.listdir("static"):
            if f.startswith("tts_") and f.endswith(".mp3"):
                try:
                    f_path = os.path.join("static", f)
                    if time.time() - os.path.getmtime(f_path) > 60:
                        os.remove(f_path)
                except: pass
                
        return jsonify({"url": f"/static/{filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def api_upload():
    files = request.files.getlist('file')
    if not files or all(f.filename == '' for f in files):
        return jsonify({"success": False, "message": "No file selected"})
    
    uploaded = []
    errors = []
    for file in files:
        if not file or file.filename == '':
            continue
        if not file.filename.lower().endswith('.pdf'):
            errors.append(f"{file.filename}: 非 PDF 檔案")
            continue
        try:
            file_content = file.read()
            supabase.storage.from_("pdfs").upload(
                path=file.filename,
                file=file_content,
                file_options={"upsert": "true"}
            )
            uploaded.append(file.filename)
        except Exception as e:
            errors.append(f"{file.filename}: {e}")
    
    msg_parts = []
    if uploaded:
        msg_parts.append(f"已上傳 {len(uploaded)} 個檔案: {', '.join(uploaded)}")
    if errors:
        msg_parts.append(f"失敗: {'; '.join(errors)}")
    return jsonify({"success": len(uploaded) > 0, "message": ' | '.join(msg_parts) or "No files processed"})

@app.route('/api/storage', methods=['GET'])
def api_list_storage():
    try:
        res = supabase.storage.from_("pdfs").list()
        files = [{"name": f['name'], "size": f.get('metadata', {}).get('size', 0)} for f in res if f['name'].lower().endswith('.pdf')]
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/storage/<path:filename>', methods=['DELETE'])
def api_delete_storage(filename):
    try:
        supabase.storage.from_("pdfs").remove([filename])
        return jsonify({"success": True, "message": f"已從雲端刪除 {filename}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/storage/<path:filename>', methods=['PUT'])
def api_rename_storage(filename):
    try:
        data = request.json
        new_name = data.get('new_name', '').strip()
        if not new_name:
            return jsonify({"success": False, "message": "新檔名不能為空"})
        if not new_name.lower().endswith('.pdf'):
            new_name += '.pdf'
        if new_name == filename:
            return jsonify({"success": True, "message": "檔名未變更"})
        # Supabase Storage 沒有 rename API，需要下載→上傳新名→刪除舊檔
        file_content = supabase.storage.from_("pdfs").download(filename)
        supabase.storage.from_("pdfs").upload(
            path=new_name,
            file=file_content,
            file_options={"upsert": "true"}
        )
        supabase.storage.from_("pdfs").remove([filename])
        return jsonify({"success": True, "message": f"已將「{filename}」更名為「{new_name}」"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/reimport', methods=['POST'])
def api_reimport():
    try:
        count = 0
        file_list = []
        duplicates = []

        # 1. Check Supabase Storage 'pdfs' bucket
        try:
            res = supabase.storage.from_("pdfs").list()
            for f in res:
                if f['name'].lower().endswith('.pdf'):
                    file_list.append({"name": f['name'], "source": "supabase"})
        except Exception as e:
            print(f"Supabase Storage List Error: {e}")

        # 2. Check local 'data' folder (for local dev)
        data_dir = "data"
        if os.path.exists(data_dir):
            for f in os.listdir(data_dir):
                if f.lower().endswith(".pdf"):
                    file_list.append({"name": f, "source": "local"})

        if not file_list:
            return jsonify({"success": False, "message": "No PDF files found in Supabase Storage or local data folder."})

        for item in file_list:
            filename = item['name']
            base_name = os.path.splitext(filename)[0]
            unit_name = base_name.upper()
            
            # Delete only this unit's existing words before reimporting
            db.delete_words_by_unit(unit_name)

            # Fetch PDF content
            if item['source'] == "supabase":
                file_content = supabase.storage.from_("pdfs").download(filename)
                # pdfplumber needs a file-like object
                import io
                pdf_file = io.BytesIO(file_content)
            else:
                pdf_file = os.path.join(data_dir, filename)

            # Collect all words for batch upsert
            batch = []
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        for row in table:
                            if not row or len(row) < 5:
                                continue
                            # 跳過任一欄位為空的列（如標題列）
                            if not all(cell and cell.strip() for cell in row[:5]):
                                continue
                            cell_text = row[1].strip()
                            if cell_text == "Word" or "單字" in cell_text: continue
                            batch.append({
                                "unit": unit_name,
                                "word": row[1].strip(),
                                "pos": row[2].strip() if row[2] else "",
                                "definition": row[3].strip() if row[3] else "",
                                "sentence": row[4].strip().replace("\n", " ") if row[4] else ""
                            })
            # Deduplicate by (unit, word) — keep last occurrence, track duplicates
            seen = {}
            for item_data in batch:
                key = (item_data["unit"], item_data["word"], item_data["pos"])
                if key in seen:
                    duplicates.append(f"  • {item_data['word']} ({item_data['pos']}) [{item_data['unit']}]")
                seen[key] = item_data
            batch = list(seen.values())
            # Batch upsert (one API call per unit instead of per word)
            if batch:
                supabase.table("words").upsert(batch, on_conflict="unit,word,pos").execute()
                count += len(batch)
        msg = f"已匯入 {count} 個單字，來自 {len(file_list)} 個檔案。"
        if duplicates:
            msg += f"\n⚠️ 發現 {len(duplicates)} 個重複單字（已自動去重）：\n" + "\n".join(duplicates)
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/users', methods=['GET'])
def api_get_users():
    return jsonify(db.get_users())

@app.route('/api/users', methods=['POST'])
def api_add_user():
    data = request.json
    name = data.get("name", "").strip()
    if not name: return jsonify({"success": False, "message": "Empty name"})
    if db.add_user(name):
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Duplicate or error"})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def api_delete_user(user_id):
    db.delete_user(user_id)
    return jsonify({"success": True})

@app.route('/api/units/<path:unit_name>', methods=['DELETE'])
def api_delete_unit(unit_name):
    try:
        db.delete_words_by_unit(unit_name)
        # Also try to remove the PDF from Supabase Storage
        # unit_name is now directly the uppercase filename, e.g. "WEEK58" -> "week58.pdf"
        pdf_name = unit_name.lower() + ".pdf"
        try:
            supabase.storage.from_("pdfs").remove([pdf_name])
        except Exception as e:
            print(f"Storage delete note: {e}")
        return jsonify({"success": True, "message": f"已刪除 {unit_name}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/units/<path:unit_name>', methods=['PUT'])
def api_rename_unit(unit_name):
    try:
        data = request.json
        new_name = data.get('new_name', '').strip()
        if not new_name:
            return jsonify({"success": False, "message": "新名稱不能為空"})
        if new_name == unit_name:
            return jsonify({"success": True, "message": "名稱未變更"})
        if db.rename_unit(unit_name, new_name):
            return jsonify({"success": True, "message": f"已將「{unit_name}」更名為「{new_name}」"})
        else:
            return jsonify({"success": False, "message": "更名失敗"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# Gmail API Helper (Global)
def get_gmail_service():
    import base64
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    creds = None

    # 1. Check for cloud environment variable (JSON string)
    creds_json = os.environ.get("GMAIL_CREDENTIALS")
    if creds_json:
        try:
            info = json.loads(creds_json)
            creds = Credentials.from_authorized_user_info(info, SCOPES)
            print(f"[Gmail] Loaded credentials from env. expired={creds.expired}, has_refresh={bool(creds.refresh_token)}")
        except Exception as e:
            print(f"[Gmail] Error loading credentials from env: {e}")

    # 2. Check for local token.json
    if not creds and os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        print(f"[Gmail] Loaded credentials from token.json. expired={creds.expired}, has_refresh={bool(creds.refresh_token)}")

    if not creds:
        print("[Gmail] No credentials found.")
        return None

    # 3. Always refresh if we have a refresh_token (don't trust expired flag)
    if creds.refresh_token:
        try:
            print("[Gmail] Attempting token refresh...")
            creds.refresh(Request())
            print("[Gmail] Token refreshed successfully.")
            # Save refreshed token locally
            if not IS_CLOUD and os.path.exists('token.json'):
                with open('token.json', 'w') as token_file:
                    token_file.write(creds.to_json())
        except Exception as e:
            print(f"[Gmail] Token refresh failed: {e}")
            # If refresh fails but token might still be valid, try anyway
            if not creds.token:
                print("[Gmail] No valid token available after refresh failure.")
                return None
            print("[Gmail] Will attempt to use existing token despite refresh failure.")

    if not creds.token:
        print("[Gmail] No token available.")
        return None

    return build('gmail', 'v1', credentials=creds)


def get_email_config():
    db_email = db.get_config("email_settings") or {}
    sender = db_email.get("sender_email")
    password = db_email.get("app_password")
    receivers = db_email.get("receivers", [])
    enable_email = db_email.get("enable", False)
    
    if not sender:
        settings = local_cfg.get("email_settings", {})
        if IS_CLOUD:
            sender = os.environ.get("GMAIL_USER", "WordApp")
            password = "oauth-token-used"
            receivers_raw = os.environ.get("RECEIVERS", "")
            receivers = [r.strip() for r in receivers_raw.split(",")] if receivers_raw else []
            enable_email = os.environ.get("ENABLE_EMAIL", "true").lower() == "true"
        else:
            sender = settings.get("sender_email")
            password = settings.get("app_password")
            receivers = settings.get("receivers", [])
            enable_email = settings.get("enable", False)
            
    return sender, password, receivers, enable_email

def send_email_message(sender, password, receivers, subject, body_html):
    import base64
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import smtplib
    
    service = get_gmail_service()
    if service:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html'))
        target_receivers = receivers if isinstance(receivers, list) else [receivers]
        msg['To'] = ", ".join(target_receivers)
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        message = {'raw': raw_message}
        sent_message = service.users().messages().send(userId="me", body=message).execute()
        return f"Gmail API (ID: {sent_message['id']})"
    elif sender and password and password != "oauth-token-used":
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html'))
        target_receivers = receivers if isinstance(receivers, list) else [receivers]
        msg['To'] = ", ".join(target_receivers)
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, target_receivers, msg.as_string())
        server.quit()
        return "SMTP Server"
    else:
        raise Exception("未設定 Gmail API OAuth，且無 SMTP 密碼，無法寄信。")


@app.route('/api/test_email', methods=['POST'])
def api_test_email():
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        sender, password, receivers, enable_email = get_email_config()
        if not receivers:
            return jsonify({"success": False, "message": "未設定收件者信箱"})
            
        subject = "[測試] Word App Email Debug"
        body_html = "<h1>🎉 Email 功能測試成功！</h1><p>這是一封來自 WordApp 的測試信。</p>"
        
        method = send_email_message(sender, password, receivers, subject, body_html)
        return jsonify({
            "success": True,
            "message": f"測試郵件已成功經由 {method} 送出至：{', '.join(receivers)}"
        })
    except Exception as e:
        logger.exception("Test Email Failed")
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/send_report', methods=['POST'])
def send_report():
    data = request.json
    unit_name = data.get('unit')
    score = data.get('score')
    total = data.get('total')
    mode = data.get('mode')
    user_name = data.get('user_name', '訪客')
    wrong_words_list = data.get('wrong_words_list', [])

    # 儲存測驗結果至資料庫
    mode_mapping = {
        "選中文": "quiz",
        "選英文": "reverse",
        "拼字": "spelling"
    }
    db_mode = mode_mapping.get(mode, "quiz")
    db.add_quiz_result(user_name, unit_name, db_mode, score, total)

    sender, password, receivers, enable_email = get_email_config()
    if not enable_email:
        return jsonify({"success": False, "message": "Email disabled"})
    if not receivers:
        return jsonify({"success": False, "message": "No receivers configured"})
        
    subject = f"[單字小學堂] 測驗完成通知 - {unit_name} ({user_name})"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    wrong_words_html = ""
    if wrong_words_list:
        rows = ""
        for w in wrong_words_list:
            definition = w.get('def') or w.get('definition', '')
            rows += f"<tr><td style='border:1px solid #ddd;padding:5px;'>{w['word']}</td><td style='border:1px solid #ddd;padding:5px;'>{definition}</td></tr>"
        
        wrong_words_html = f"""
        <h3>⚠️ 錯題檢討</h3>
        <table style='border-collapse:collapse; width:100%; max-width:600px;'>
            <tr style='background-color:#f2f2f2;'>
                <th style='border:1px solid #ddd;padding:8px;'>單字</th>
                <th style='border:1px solid #ddd;padding:8px;'>中文解釋</th>
            </tr>
            {rows}
        </table>
        """
    else:
        wrong_words_html = "<p style='color:green'>🎉 太棒了！本次測驗沒有答錯的題目！</p>"
    
    body = f"""
    <html>
    <body>
        <h2>🎉 測驗完成通知</h2>
        <p><strong>使用者：</strong> {user_name}</p>
        <p><strong>時間：</strong> {current_time}</p>
        <p><strong>單元：</strong> {unit_name}</p>
        <p><strong>模式：</strong> {mode}</p>
        <hr>
        <h3>📊 成績報告</h3>
        <ul>
            <li><strong>答對題數：</strong> <span style="color:green">{score}</span></li>
            <li><strong>總題數：</strong> {total}</li>
            <li><strong>正確率：</strong> {int((score/total)*100) if total > 0 else 0}%</li>
        </ul>
        <hr>
        {wrong_words_html}
        <p>繼續加油！💪</p>
    </body>
    </html>
    """
    
    def _send():
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        try:
            logger.info("Sending report email in background...")
            method = send_email_message(sender, password, receivers, subject, body)
            logger.info(f"Report email sent successfully via {method}")
        except Exception as e:
            logger.exception("Email API Critical Error")

    threading.Thread(target=_send, daemon=True).start()
    return jsonify({"success": True})


@app.route('/api/review_progress', methods=['GET'])
def api_review_progress():
    try:
        r_settings = db.get_config("review_settings") or {}
        config_start = r_settings.get("start_date", "2026-07-01")
        config_end = r_settings.get("end_date", "2026-08-31")
        required_days = r_settings.get("required_days", 2)
        selected_units = r_settings.get("selected_units", [])

        start_date = f"{config_start}T00:00:00+08:00"
        end_date = f"{config_end}T23:59:59+08:00"

        records = db.get_review_progress_records(start_date, end_date)
        all_units = db.get_units()
        
        if selected_units:
            units = [u for u in all_units if u in selected_units]
        else:
            units = all_units

        users = [u['name'] for u in db.get_users()]

        valid_records = []
        for r in records:
            u_name = r.get("user_name")
            u_unit = r.get("unit")
            u_mode = r.get("mode")
            u_accuracy = r.get("accuracy", 0.0)
            created_at_str = r.get("created_at")

            if u_name in users and u_unit in units and u_accuracy >= 90.0:
                local_date = config_start
                try:
                    from datetime import datetime, timezone, timedelta
                    dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    local_dt = dt.astimezone(timezone(timedelta(hours=8)))
                    local_date = local_dt.strftime("%Y-%m-%d")
                except Exception as ex:
                    print(f"Date Parse Error: {ex}")
                    if created_at_str and len(created_at_str) >= 10:
                        local_date = created_at_str[:10]

                valid_records.append({
                    "user_name": u_name,
                    "unit": u_unit,
                    "mode": u_mode,
                    "accuracy": u_accuracy,
                    "date": local_date
                })

        return jsonify({
            "success": True,
            "units": units,
            "users": users,
            "records": valid_records,
            "required_days": required_days,
            "start_date": config_start,
            "end_date": config_end
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500



if __name__ == '__main__':
    load_config() # Create config.json if not exists
    ip = get_local_ip()
    print(f"========================================")
    print(f" 網頁版已啟動！")
    print(f" 請在瀏覽器輸入以下網址 (本機): http://localhost:5001")
    print(f" 請在手機/其他電腦輸入 (Wi-Fi): http://{ip}:5001")
    print(f"========================================")
    app.run(host='0.0.0.0', port=5001, debug=True)
