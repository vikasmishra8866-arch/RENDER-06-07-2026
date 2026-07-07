import os
import asyncio
import threading
from flask import Flask, request, jsonify, render_template_string

# --- इवेंट लूप फिक्स ---
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

app = Flask(__name__)

# Render Environment Variables
API_ID = int(os.getenv("TG_API_ID", "30587359"))
API_HASH = os.getenv("TG_API_HASH", "841b57b9782c258672af34c5f7146f56")
BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "@rtovehicleinfoobot").strip()

if not BOT_USERNAME.startswith("@"):
    BOT_USERNAME = "@" + BOT_USERNAME

# रेंडर पर सेशन डिलीट न हो, इसलिए लोकल डिस्क पर स्टोर करेंगे
SESSION_PATH = "/opt/render/project/src/telegram_session" if os.path.exists("/opt/render/project/src") else "telegram_session"

def start_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

# क्लाइंट को परमानेंट सेशन फ़ाइल के साथ शुरू करना
client = TelegramClient(SESSION_PATH, API_ID, API_HASH, loop=loop)

# ग्लोबल डिक्शनरी ताकि लॉगिन प्रोग्रेस ट्रैक हो सके
login_state = {"phone": None, "phone_code_hash": None}

# HTML इंटरफ़ेस (लॉगिन + व्हीकल सर्च दोनों एक ही जगह)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Parivahan Service Automation</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; text-align: center; }
        .card { max-width: 500px; margin: 40px auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); border: 1px solid #e1e4e8; }
        h2 { color: #2c3e50; margin-bottom: 10px; }
        p { color: #7f8c8d; font-size: 14px; }
        input[type="text"], input[type="password"] { width: 85%; padding: 12px; margin: 10px 0; border: 2px solid #cbd5e1; border-radius: 6px; font-size: 16px; outline: none; }
        input:focus { border-color: #3498db; }
        button { background-color: #27ae60; color: white; border: none; padding: 12px 20px; font-size: 16px; border-radius: 6px; cursor: pointer; width: 90%; font-weight: bold; margin-top: 10px; }
        button:hover { background-color: #219653; }
        .btn-auth { background-color: #2f80ed; }
        .btn-auth:hover { background-color: #1b60c4; }
        .status-box { margin-top: 20px; padding: 12px; border-radius: 6px; font-weight: bold; background-color: #f8f9fa; text-align: left; word-wrap: break-word; font-size: 14px; }
    </style>
</head>
<body>

<div class="card">
    <h2>🚗 Parivahan Service System</h2>
    <p>टेलीग्राम सेशन को चालू रखने और ऑटो-क्लिकर बटन दबाने का मास्टर पैनल।</p>
    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">

    <div id="auth_section">
        <h4 style="color: #2f80ed; margin: 5px 0;">🔑 टेलीग्राम ऑथेंटिकेशन</h4>
        <p>अगर आपकी वेबसाइट पर पहली बार आए हैं, तो नीचे अपना टेलीग्राम नंबर डालकर OTP मंगाएं।</p>
        <input type="text" id="phone_input" placeholder="+919999999999">
        <button onclick="sendOtp()" class="btn-auth">1. OTP भेजें 📩</button>
        
        <div id="otp_div" style="display:none; margin-top: 15px;">
            <input type="text" id="otp_input" placeholder="टेलीग्राम ऐप में आया कोड डालें">
            <button onclick="verifyOtp()" class="btn-auth" style="background-color: #8e44ad;">2. कोड वेरीफाई करें ✅</button>
        </div>
    </div>

    <hr style="border: 0; border-top: 1px solid #eee; margin: 25px 0;">

    <div>
        <h4 style="color: #27ae60; margin: 5px 0;">🔍 व्हीकल नंबर सर्च</h4>
        <input type="text" id="v_number" placeholder="GJ05MS9717" style="text-transform: uppercase;">
        <button onclick="searchVehicle()">ऑटो-क्लिक बोट रन करें 🚀</button>
    </div>

    <div id="status_box" class="status-box">स्थिति: तैयार है। टेलीग्राम लॉगिन चेक करें या सीधे गाड़ी नंबर टेस्ट करें।</div>
</div>

<script>
let box = document.getElementById('status_box');

async def_post(url, body) {
    let res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    return await res.json();
}

async function sendOtp() {
    let phone = document.getElementById('phone_input').value.trim();
    if(!phone) return alert('कृपया नंबर डालें!');
    box.innerHTML = '⏳ टेलीग्राम सर्वर से कोड (OTP) का अनुरोध किया जा रहा है...';
    
    let data = await def_post('/send-otp', { phone: phone });
    if(data.status === 'otp_sent') {
        box.style.color = '#2f80ed';
        box.innerHTML = '📩 कोड आपके टेलीग्राम ऐप पर भेज दिया गया है! कृपया उसे नीचे दर्ज करें।';
        document.getElementById('otp_div').style.display = 'block';
    } else {
        box.style.color = '#c0392b';
        box.innerHTML = '❌ एरर: ' + data.message;
    }
}

async function verifyOtp() {
    let code = document.getElementById('otp_input').value.trim();
    if(!code) return alert('कृपया कोड डालें!');
    box.innerHTML = '⏳ कोड वेरीफाई किया जा रहा है और सुरक्षित सत्र फ़ाइल बनाई जा रही है...';
    
    let data = await def_post('/verify-otp', { code: code });
    if(data.status === 'success') {
        box.style.color = '#27ae60';
        box.innerHTML = '✅ टेलीग्राम सफलतापूर्वक लिंक हो गया है! अब आप हमेशा के लिए गाड़ी नंबर सर्च कर सकते हैं।';
        document.getElementById('auth_section').style.display = 'none';
    } else {
        box.style.color = '#c0392b';
        box.innerHTML = '❌ एरर: ' + data.message;
    }
}

async function searchVehicle() {
    let num = document.getElementById('v_number').value.trim();
    if(!num) return alert('कृपया गाड़ी नंबर डालें!');
    box.style.color = '#d35400';
    box.innerHTML = '⏳ बोट के बटन पर ऑटो-क्लिक किया जा रहा है और डिटेल्स निकाली जा रही हैं... (15 सेकंड रुकें)';
    
    let data = await def_post('/search', { vehicle_number: num });
    if(data.status === 'success') {
        box.style.color = '#27ae60';
        box.innerHTML = '✅ <b>बोट रिस्पॉन्स:</b><br><br>' + data.reply.replace(/\\n/g, '<br>');
    } else {
        box.style.color = '#c0392b';
        box.innerHTML = '❌ <b>सर्च एरर:</b> ' + data.message;
    }
}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

# --- टेलीग्राम ऑथेंटिकेशन एंडपॉइंट्स ---
async def _send_otp_tg(phone):
    if not client.is_connected():
        await client.connect()
    sent = await client.send_code_request(phone)
    login_state["phone"] = phone
    login_state["phone_code_hash"] = sent.phone_code_hash

@app.route('/send-otp', methods=['POST'])
def send_otp_route():
    try:
        phone = request.json.get('phone', '').strip()
        future = asyncio.run_coroutine_threadsafe(_send_otp_tg(phone), loop)
        future.result()
        return jsonify({"status": "otp_sent"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

async def _verify_otp_tg(code):
    await client.sign_in(login_state["phone"], code, phone_code_hash=login_state["phone_code_hash"])

@app.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    try:
        code = request.json.get('code', '').strip()
        future = asyncio.run_coroutine_threadsafe(_verify_otp_tg(code), loop)
        future.result()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# --- ऑटो-क्लिकर और डेटा सर्च लॉजिक ---
async def _execute_bot_flow(gadi_num):
    if not client.is_connected():
        await client.connect()
    
    if not await client.is_user_authorized():
        return {"status": "error", "message": "आपका टेलीग्राम अकाउंट सर्वर से लिंक नहीं है। कृपया पहले ऊपर लॉगिन करें।"}
    
    # 1. बोट एंटिटी खोजना (लॉगिन होने के बाद यह तुरंत मिल जाएगी)
    bot_entity = await client.get_input_entity(BOT_USERNAME)
    
    # 2. बोट को /start भेजकर कीबोर्ड लोड करना
    await client.send_message(bot_entity, "/start")
    await asyncio.sleep(3)
    
    button_clicked = False
    
    # 3. बोट चैट के अंदर 'Vehicle Details' बटन खोजना और उसपर ऑटो-क्लिक सिमुलेट करना
    async for message in client.iter_messages(bot_entity, limit=1):
        if message.reply_markup and hasattr(message.reply_markup, 'rows'):
            for row in message.reply_markup.rows:
                for button in row.buttons:
                    if "vehicle" in button.text.lower():
                        await client.send_message(bot_entity, button.text)
                        button_clicked = True
                        break
                if button_clicked: break

    if not button_clicked:
        return {"status": "error", "message": "बोट का 'Vehicle Details' कीबोर्ड बटन स्क्रीन पर नहीं मिला।"}
        
    await asyncio.sleep(3) # "Enter vehicle number" का इंतज़ार
    
    # 4. गाड़ी नंबर भेजना
    await client.send_message(bot_entity, gadi_num)
    
    # 5. ₹5 कटने और डेटा रेंडर होने का इंतज़ार (12 सेकंड)
    await asyncio.sleep(12)
    
    # 6. बोट का आखिरी जवाब खींचना
    async for message in client.iter_messages(bot_entity, limit=1):
        return {"status": "success", "reply": message.text}
        
    return {"status": "error", "message": "नंबर भेजने के बाद बोट से कोई रिस्पॉन्स नहीं मिला।"}

@app.route('/search', methods=['POST'])
def search_route():
    try:
        gadi_number = request.json.get('vehicle_number', '').strip().upper()
        future = asyncio.run_coroutine_threadsafe(_execute_bot_flow(gadi_number), loop)
        return jsonify(future.result())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
