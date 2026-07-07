import os
import asyncio
import threading
import base64
from flask import Flask, request, jsonify, render_template_string

# --- इवेंट लूप फिक्स ---
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from telethon import TelegramClient

app = Flask(__name__)

# Render Environment Variables
API_ID = int(os.getenv("TG_API_ID", "30587359"))
API_HASH = os.getenv("TG_API_HASH", "841b57b9782c258672af34c5f7146f56")
BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "@rtovehicleinfoobot").strip()

if not BOT_USERNAME.startswith("@"):
    BOT_USERNAME = "@" + BOT_USERNAME

SESSION_PATH = "telegram_session"

def start_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()
client = TelegramClient(SESSION_PATH, API_ID, API_HASH, loop=loop)

# QR कोड की स्थिति को ट्रैक करने के लिए ग्लोबल वेरिएबल
qr_state = {"qr_link": None, "token": None, "client_instance": client}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Parivahan Service QR Automation</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; text-align: center; }
        .card { max-width: 500px; margin: 40px auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0px 4px 10px rgba(0,0,0,0.1); border: 1px solid #e1e4e8; }
        h2 { color: #2c3e50; margin-bottom: 10px; }
        p { color: #7f8c8d; font-size: 14px; }
        input[type="text"] { width: 85%; padding: 12px; margin: 10px 0; border: 2px solid #cbd5e1; border-radius: 6px; font-size: 16px; outline: none; text-transform: uppercase; }
        button { background-color: #27ae60; color: white; border: none; padding: 12px 20px; font-size: 16px; border-radius: 6px; cursor: pointer; width: 90%; font-weight: bold; margin-top: 10px; }
        button:hover { background-color: #219653; }
        .btn-qr { background-color: #2f80ed; }
        .btn-qr:hover { background-color: #1b60c4; }
        .status-box { margin-top: 20px; padding: 12px; border-radius: 6px; font-weight: bold; background-color: #f8f9fa; text-align: left; word-wrap: break-word; font-size: 14px; }
        #qr_img { width: 220px; height: 220px; margin: 15px auto; border: 4px solid #34495e; padding: 5px; background: white; display: none; }
    </style>
</head>
<body>

<div class="card">
    <h2>🚗 Parivahan Service Panel</h2>
    <p>QR कोड स्कैन करके अपने टेलीग्राम को 1 सेकंड में सर्वर से लिंक करें।</p>
    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">

    <div id="qr_section">
        <h4 style="color: #2f80ed; margin: 5px 0;">📲 टेलीग्राम लॉगिन (QR स्कैन करें)</h4>
        <p>नीचे बटन दबाएं, फिर अपने टेलीग्राम ऐप के Settings -> Devices -> Link Desktop Device में जाकर इसे स्कैन करें।</p>
        <button onclick="generateQR()" class="btn-qr">1. QR कोड जेनरेट करें 🖼️</button>
        <br>
        <img id="qr_img" src="" alt="Telegram QR Code">
    </div>

    <hr style="border: 0; border-top: 1px solid #eee; margin: 25px 0;">

    <div>
        <h4 style="color: #27ae60; margin: 5px 0;">🔍 व्हीकल नंबर सर्च</h4>
        <input type="text" id="v_number" placeholder="GJ05MS9717">
        <button onclick="searchVehicle()">ऑटो-क्लिक बोट रन करें 🚀</button>
    </div>

    <div id="status_box" class="status-box">स्थिति: तैयार है। पहले QR कोड स्कैन करें या सीधे गाड़ी नंबर चलाएं।</div>
</div>

<script>
let box = document.getElementById('status_box');
let qrImg = document.getElementById('qr_img');
let checkInterval = null;

async function generateQR() {
    box.style.color = '#2f80ed';
    box.innerHTML = '⏳ टेलीग्राम सर्वर से QR कोड लाया जा रहा है... कृपया रुकें...';
    
    let res = await fetch('/generate-qr', { method: 'POST' });
    let data = await res.json();
    
    if(data.status === 'qr_ready') {
        qrImg.src = "data:image/png;base64," + data.image;
        qrImg.style.display = 'block';
        box.innerHTML = '✅ QR कोड तैयार है! अपने फोन के टेलीग्राम से इसे तुरंत स्कैन करें।';
        
        // हर 3 सेकंड में चेक करना कि यूज़र ने स्कैन किया या नहीं
        if(checkInterval) clearInterval(checkInterval);
        checkInterval = setInterval(checkLoginStatus, 3000);
    } else {
        box.style.color = '#c0392b';
        box.innerHTML = '❌ एरर: ' + data.message;
    }
}

async function checkLoginStatus() {
    let res = await fetch('/check-qr-status');
    let data = await res.json();
    if(data.status === 'logged_in') {
        clearInterval(checkInterval);
        qrImg.style.display = 'none';
        box.style.color = '#27ae60';
        box.innerHTML = '🎉 बधाई हो विकास भाई! टेलीग्राम सफलतापूर्वक लिंक हो गया है। अब आप गाड़ी सर्च कर सकते हैं!';
    } else if (data.status === 'expired') {
        clearInterval(checkInterval);
        qrImg.style.display = 'none';
        box.style.color = '#c0392b';
        box.innerHTML = '❌ QR कोड की समय सीमा समाप्त हो गई। कृपया दोबारा बटन दबाएं।';
    }
}

async function searchVehicle() {
    let num = document.getElementById('v_number').value.trim();
    if(!num) return alert('कृपया गाड़ी नंबर डालें!');
    box.style.color = '#d35400';
    box.innerHTML = '⏳ बोट पर ऑटो-क्लिक किया जा रहा है... (12-15 सेकंड रुकें)...';
    
    let res = await fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_number: num })
    });
    let data = await res.json();
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

# --- QR कोड जनरेशन एंडपॉइंट ---
async def _async_qr_flow():
    if not client.is_connected():
        await client.connect()
    
    # टेलीथॉन का इन-बिल्ट QR लॉगिन मैनेजर
    qr_login = await client.qr_login()
    qr_state["token"] = qr_login
    
    # QR कोड को इमेज (Bytes) में बदलना ताकि स्क्रीन पर दिखा सकें
    import qrcode
    from io import BytesIO
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_login.url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_str

@app.route('/generate-qr', methods=['POST'])
def generate_qr_route():
    try:
        future = asyncio.run_coroutine_threadsafe(_async_qr_flow(), loop)
        img_base64 = future.result()
        return jsonify({"status": "qr_ready", "image": img_base64})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# --- स्टेटस चेक एंडपॉइंट ---
async def _async_check_qr():
    token = qr_state.get("token")
    if not token:
        return "expired"
    try:
        # यह चेक करता है कि यूजर ने स्कैन पूरा किया या नहीं
        await token.wait(timeout=2)
        return "logged_in"
    except asyncio.TimeoutError:
        return "waiting"
    except Exception:
        return "expired"

@app.route('/check-qr-status')
def check_qr_status():
    future = asyncio.run_coroutine_threadsafe(_async_check_qr(), loop)
    res = future.result()
    return jsonify({"status": res})

# --- ऑटो-क्लिकर और डेटा सर्च लॉजिक ---
async def _execute_bot_flow(gadi_num):
    if not client.is_connected():
        await client.connect()
    
    if not await client.is_user_authorized():
        return {"status": "error", "message": "टेलीग्राम लिंक नहीं है। कृपया पहले ऊपर QR कोड स्कैन करें।"}
    
    bot_entity = await client.get_input_entity(BOT_USERNAME)
    await client.send_message(bot_entity, "/start")
    await asyncio.sleep(3)
    
    button_clicked = False
    async range_msg in [client.iter_messages(bot_entity, limit=1)]:
        async for message in range_msg:
            if message.reply_markup and hasattr(message.reply_markup, 'rows'):
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        if "vehicle" in button.text.lower():
                            await client.send_message(bot_entity, button.text)
                            button_clicked = True
                            break
                    if button_clicked: break

    if not button_clicked:
        return {"status": "error", "message": "बोट का 'Vehicle Details' बटन नहीं मिला।"}
        
    await asyncio.sleep(3)
    await client.send_message(bot_entity, gadi_num)
    await asyncio.sleep(12)
    
    async for message in client.iter_messages(bot_entity, limit=1):
        return {"status": "success", "reply": message.text}
        
    return {"status": "error", "message": "बोट से कोई रिस्पॉन्स नहीं आया।"}

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
