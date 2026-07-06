import os
import re
import asyncio
import threading
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "super_secret_key_101")

# Telegram Credentials (.env से लोड होंगे)
API_ID = int(os.getenv("TG_API_ID", "123456"))  # अपना असली API ID डालें
API_HASH = os.getenv("TG_API_HASH", "your_api_hash_here")
BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "@YourVehicleBotName")

# SQLite Database Helper (बिना किसी झंझट के लोकल डेटाबेस)
import sqlite3
DB_FILE = "database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # यूज़र्स टेबल (Points कॉलम के साथ)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user'
        )
    ''')
    # डिफ़ॉल्ट एडमिन और टेस्ट यूजर बनाना (यदि पहले से न हो)
    try:
        cursor.execute("INSERT INTO users (username, password, points, role) VALUES ('admin', 'admin123', 9999, 'admin')")
        cursor.execute("INSERT INTO users (username, password, points, role) VALUES ('user1', 'user123', 10, 'user')")
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

init_db()

# Telethon Client को बैकग्राउंड में चालू रखने का सेटअप
loop = asyncio.new_event_loop()

def start_telethon_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_telethon_loop, args=(loop,), daemon=True).start()

client = TelegramClient('parivahan_session', API_ID, API_HASH, loop=loop)
asyncio.run_coroutine_threadsafe(client.start(), loop)

# बॉट के मैसेज से डेटा निकालने का Regex फंक्शन (प्रीमियम क्लीनर)
def parse_bot_message(text):
    data = {
        "reg_no": re.search(r"VEHICLE DETAILS:\s*(\w+)", text),
        "owner_name": re.search(r"Owner Name:\s*(.*)", text),
        "father_name": re.search(r"Father's Name:\s*(.*)", text),
        "mobile": re.search(r"Mobile Number:\s*(\d+)", text),
        "model": re.search(r"Model:\s*(.*)", text),
        "fuel": re.search(r"Fuel Type:\s*(.*)", text),
        "chassis": re.search(r"Chassis Number:\s*(.*)", text),
        "engine": re.search(r"Engine Number:\s*(.*)", text),
        "status": re.search(r"Status:\s*(\w+)", text),
    }
    # क्लीन करके केवल वैल्यू निकालना
    clean_data = {}
    for key, val in data.items():
        clean_data[key] = val.group(1).strip() if val else "N/A"
    return clean_data

# --- FLASK ROUTES ---

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['username'] = user[0]
            session['role'] = user[1]
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="गलत यूज़रनेम या पासवर्ड!")
        
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT points FROM users WHERE username=?", (session['username'],))
    points = cursor.fetchone()[0]
    conn.close()
    
    return render_template('dashboard.html', username=session['username'], points=points, role=session['role'])

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'username' not in session or session.get('role') != 'admin':
        return "Access Denied!", 403
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        target_user = request.form['username']
        action = request.form['action']
        amount = int(request.form['amount'])
        
        if action == 'add':
            cursor.execute("UPDATE users SET points = points + ? WHERE username = ?", (amount, target_user))
        elif action == 'set':
            cursor.execute("UPDATE users SET points = ? WHERE username = ?", (amount, target_user))
        conn.commit()
        
    cursor.execute("SELECT id, username, points, role FROM users")
    all_users = cursor.fetchall()
    conn.close()
    return render_template('admin.html', users=all_users)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- मुख्य सर्च API (पॉइंट्स माइनस लॉजिक के साथ) ---
async def fetch_from_telegram(gadi_number):
    # बॉट को मैसेज सेंड करना
    await client.send_message(BOT_USERNAME, gadi_number)
    
    # रिप्लाई का इंतज़ार करने के लिए फ्यूचर ऑब्जेक्ट
    fut = loop.create_future()
    
    @client.on(events.NewMessage(from_users=BOT_USERNAME))
    async def handler(event):
        if gadi_number in event.raw_text or "VEHICLE" in event.raw_text:
            client.remove_event_handler(handler)
            if not fut.done():
                fut.set_result(event.raw_text)
                
    try:
        # 15 सेकंड का टाइमआउट ताकि स्क्रिप्ट हमेशा के लिए न फंसी रहे
        response_text = await asyncio.wait_for(fut, timeout=15.0)
        return parse_bot_message(response_text)
    except asyncio.TimeoutError:
        client.remove_event_handler(handler)
        return {"error": "टेलीग्राम बॉट ने समय पर जवाब नहीं दिया।"}

@app.route('/api/search', methods=['POST'])
def search_vehicle():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    gadi_number = request.json.get('vehicle_number', '').strip().upper()
    if not gadi_number:
        return jsonify({"error": "कृपया सही गाड़ी नंबर डालें।"}), 400
        
    username = session['username']
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT points FROM users WHERE username=?", (username,))
    current_points = cursor.fetchone()[0]
    
    if current_points <= 0:
        conn.close()
        return jsonify({"error": "आपके पास पर्याप्त पॉइंट्स नहीं हैं! कृपया एडमिन से रिचार्ज करवाएं।"}), 403
        
    # बैकग्राउंड टेलीग्राम कॉल को सिंक्रोनस तरीके से रन करना
    future = asyncio.run_coroutine_threadsafe(fetch_from_telegram(gadi_number), loop)
    result = future.result()
    
    if "error" not in result:
        # सर्च सफल होने पर ही 1 पॉइंट माइनस होगा
        cursor.execute("UPDATE users SET points = points - 1 WHERE username=?", (username,))
        conn.commit()
        
    cursor.execute("SELECT points FROM users WHERE username=?", (username,))
    updated_points = cursor.fetchone()[0]
    conn.close()
    
    result['updated_points'] = updated_points
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
