import os
import re
import asyncio
import threading
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

# रेंडर पाथ फिक्स
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, 'templates')

app = Flask(__name__, template_folder=template_dir)
app.secret_key = os.getenv("FLASK_SECRET", "ParivahanServiceUltraPremiumKey2026")

# Telegram Credentials
API_ID = int(os.getenv("TG_API_ID", "30587359"))
API_HASH = os.getenv("TG_API_HASH", "841b57b9782c258672af34c5f7146f56")
BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "@rtovehicleinfoobot")

# --- MEMORY DATABASE FIX ---
# फाइल सिस्टम का झंझट ही खत्म, डेटाबेस सीधे रैम में चलेगा ताकि लॉक एरर न आए
DB_FILE = ":memory:"

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            role TEXT DEFAULT 'user'
        )
    ''')
    try:
        cursor.execute("INSERT INTO users (username, password, points, role) VALUES ('admin', 'admin123', 9999, 'admin')")
        cursor.execute("INSERT INTO users (username, password, points, role) VALUES ('user1', 'user123', 10, 'user')")
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    return conn

# ग्लोबल कनेक्शन जो कभी बंद नहीं होगा
db_conn = init_db()

# --- EVENT LOOP FIX ---
loop = asyncio.new_event_loop()
def start_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

# टेलीग्राम क्लाइंट बिना किसी फाइल सेशन के (Memory Session)
client = TelegramClient(None, API_ID, API_HASH, loop=loop)

# --- ROUTES ---
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
        
        cursor = db_conn.cursor()
        cursor.execute("SELECT username, role FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        
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
        
    cursor = db_conn.cursor()
    cursor.execute("SELECT points FROM users WHERE username=?", (session['username'],))
    points = cursor.fetchone()[0]
    return render_template('dashboard.html', username=session['username'], points=points, role=session['role'])

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'username' not in session or session.get('role') != 'admin':
        return "Access Denied!", 403
        
    cursor = db_conn.cursor()
    if request.method == 'POST':
        target_user = request.form['username']
        action = request.form['action']
        amount = int(request.form['amount'])
        if action == 'add':
            cursor.execute("UPDATE users SET points = points + ? WHERE username = ?", (amount, target_user))
        elif action == 'set':
            cursor.execute("UPDATE users SET points = ? WHERE username = ?", (amount, target_user))
        db_conn.commit()
        
    cursor.execute("SELECT id, username, points, role FROM users")
    all_users = cursor.fetchall()
    return render_template('admin.html', users=all_users)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def parse_bot_message(text):
    data = {
        "reg_no": re.search(r"Registration Number:\s*([\w\-]+)", text, re.IGNORECASE),
        "owner_name": re.search(r"Owner Name:\s*(.*)", text, re.IGNORECASE),
    }
    return {k: (v.group(1).strip() if v else "NA") for k, v in data.items()}

async def fetch_from_telegram(gadi_number):
    if not client.is_connected():
        await client.connect()
    await client.send_message(BOT_USERNAME, gadi_number)
    fut = loop.create_future()
    
    @client.on(events.NewMessage(from_users=BOT_USERNAME))
    async def handler(event):
        if gadi_number in event.raw_text or "VEHICLE" in event.raw_text:
            client.remove_event_handler(handler)
            if not fut.done():
                fut.set_result(event.raw_text)
    try:
        response_text = await asyncio.wait_for(fut, timeout=15.0)
        return parse_bot_message(response_text)
    except asyncio.TimeoutError:
        client.remove_event_handler(handler)
        return {"error": "Timeout"}

@app.route('/api/search', methods=['POST'])
def search_vehicle():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    gadi_number = request.json.get('vehicle_number', '').strip().upper()
    future = asyncio.run_coroutine_threadsafe(fetch_from_telegram(gadi_number), loop)
    return jsonify(future.result())

if __name__ == '__main__':
    app.run(debug=True, port=5000)
