import os
import asyncio
import threading
import base64
from flask import Flask, request, jsonify, render_template_string

# --- इवेंट लूप सेटअप ---
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def start_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

from telethon import TelegramClient

app = Flask(__name__)

# Environment Variables
API_ID = int(os.getenv("TG_API_ID", "30587359"))
API_HASH = os.getenv("TG_API_HASH", "841b57b9782c258672af34c5f7146f56")
BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "@rtovehicleinfoobot").strip()

if not BOT_USERNAME.startswith("@"):
    BOT_USERNAME = "@" + BOT_USERNAME

SESSION_PATH = "telegram_session"
client = TelegramClient(SESSION_PATH, API_ID, API_HASH, loop=loop)
qr_state = {"token": None}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Parivahan Service Panel</title>
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
        .status-box { margin-top: 20px; padding: 12px; border-radius: 6px; font-weight: bold; background-color: #f8f9fa; text-align: left; word-wrap: break-word; font-size: 14px; min-height: 40px; white-space: pre-line; }
        #qr_img { width: 220px; height: 220px; margin: 15px auto; border: 4px solid #34495e; padding: 5px; background: white; display: none; }
    </style>
</head>
<body>

<div class="card">
    <h2>🚗 Parivahan Service Panel</h2>
    <p>QR कोड स्कैन करके अपने टेलीग्राम को सर्वर से लिंक करें।</p>
    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">

    <div id="qr_section">
        <h4 style="color: #2f80ed; margin: 5px 0;">📲 टेलीग्राम लॉगिन (QR स्कैन)</h4>
        <button onclick="generateQR()" class="btn-qr">1. QR कोड जेनरेट करें 🖼️</button>
        <br>
        <img id="qr_img" src="" alt="Telegram QR Code">
    </div>

    <hr style="border: 0; border-top: 1px solid #eee; margin: 25px 0;">

    <div>
        <h4 style="color: #27ae60; margin: 5px 0;">🔍 व्हीकल नंबर सर्च</h4>
        <input type="text" id="v_number" placeholder="GJ05CT3847" value="GJ05CT3847">
        <button onclick="searchVehicle()">ऑटो-क्लिक बोट रन करें 🚀</button>
    </div>

    <div id="status_box" class="status-box">स्थिति: तैयार है।</div>
</div>

<script>
let box = document.getElementById('status_box');
let qrImg = document.getElementById('qr_img');
let checkInterval = null;

async function generateQR() {
    box.style.color = '#2f80ed';
    box.innerHTML = '⏳ क्यूआर कोड जेनरेट हो रहा है...';
    qrImg.style.display = 'none';
    try {
        let res = await fetch('/generate-qr', { method: 'POST' });
        let data = await res.json();
        if(data.status === 'qr_ready') {
            if(data.message === 'already_logged_in') {
                box.style.color = '#27ae60';
                box.innerHTML = '🎉 आप पहले से लॉग इन हैं! सीधे सर्च करें।';
                return;
            }
            qrImg.src = "data:image/png;base64," + data.image;
            qrImg.style.display = 'block';
            box.innerHTML = '✅ QR स्कैन करें।';
            if(checkInterval) clearInterval(checkInterval);
            checkInterval = setInterval(checkLoginStatus, 3000);
        }
    } catch (e) {}
}

async function checkLoginStatus() {
    try {
        let res = await fetch('/check-qr-status');
        let data = await res.json();
        if(data.status === 'logged_in') {
            clearInterval(checkInterval);
            qrImg.style.display = 'none';
            box.style.color = '#27ae60';
            box.innerHTML = '🎉 लिंक हो गया!';
        }
    } catch(e) {}
}

async function searchVehicle() {
    let num = document.getElementById('v_number').value.trim();
    if(!num) return alert('गाड़ी नंबर डालें!');
    box.style.color = '#d35400';
    box.innerHTML = '⏳ बोट पर असली इनलाइन बटन क्लिक किया जा रहा है... कृपया 15 सेकंड रुकें...';
    
    try {
        let res = await fetch('/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_number: num })
        });
        let data = await res.json();
        if(data.status === 'success') {
            box.style.color = '#2c3e50';
            box.innerHTML = '✅ <b>डिटेल्स:</b>\\n\\n' + data.reply;
        } else {
            box.style.color = '#c0392b';
            box.innerHTML = '❌ एरर: ' + data.message;
        }
    } catch (e) {
        box.style.color = '#c0392b';
        box.innerHTML = '❌ कनेक्शन फेल।';
    }
}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate-qr', methods=['POST'])
def generate_qr_route():
    try:
        future = asyncio.run_coroutine_threadsafe(_async_qr_flow(), loop)
        result = future.result()
        if isinstance(result, dict) and result.get("already_logged_in"):
            return jsonify({"status": "qr_ready", "image": "", "message": "already_logged_in"})
        return jsonify({"status": "qr_ready", "image": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

async def _async_qr_flow():
    if not client.is_connected(): await client.connect()
    if await client.is_user_authorized(): return {"already_logged_in": True}
    qr_login = await client.qr_login()
    qr_state["token"] = qr_login
    import qrcode
    from io import BytesIO
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_login.url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@app.route('/check-qr-status')
def check_qr_status():
    try:
        future = asyncio.run_coroutine_threadsafe(_async_check_qr(), loop)
        return jsonify({"status": future.result()})
    except Exception:
        return jsonify({"status": "waiting"})

async def _async_check_qr():
    token = qr_state.get("token")
    if not token:
        if await client.is_user_authorized(): return "logged_in"
        return "expired"
    try:
        await token.wait(timeout=1)
        return "logged_in"
    except Exception:
        return "waiting"

# --- [एडवांस अपडेट]: असली इनलाइन बटन को डिटेक्ट और क्लिक करने का फ्लो ---
async def _execute_bot_flow(gadi_num):
    if not client.is_connected(): 
        await client.connect()
    if not await client.is_user_authorized():
        return {"status": "error", "message": "पहले लॉगिन करें।"}
        
    bot_entity = await client.get_input_entity(BOT_USERNAME)
    
    # स्टेप 1: फ्रेश /start कमांड भेजें
    await client.send_message(bot_entity, "/start")
    await asyncio.sleep(3.5)
    
    # स्टेप 2: बोट का आखिरी मैसेज लाकर बटन ढूंढें
    messages = await client.get_messages(bot_entity, limit=1)
    clicked = False
    
    if messages:
        msg = messages[0]
        # चेक करें कि क्या बोट के पास रिप्लाई बटन मेनू है
        if msg.reply_markup:
            # तरीके 1: असली इनलाइन या कीबोर्ड बटन पर क्लिक इवेंट ट्रिगर करना
            try:
                for row_idx, row in enumerate(msg.reply_markup.rows):
                    for btn_idx, button in enumerate(row.buttons):
                        if "vehicle" in button.text.lower() or "details" in button.text.lower():
                            # सीधे बटन ऑब्जेक्ट पर क्लिक करें (यह असली माउस क्लिक जैसा काम करेगा)
                            await msg.click(row_idx, btn_idx)
                            clicked = True
                            break
                    if clicked: break
            except Exception:
                clicked = False

    # सेफ्टी नेट: अगर बोट क्लिक ब्लॉक कर रहा है, तो टेक्स्ट के रूप में भेजें
    if not clicked:
        await client.send_message(bot_entity, "🚘 Vehicle Details + Contact")
    
    await asyncio.sleep(4) # बटन रिस्पॉन्स के लिए रुकें
    
    # स्टेप 3: गाड़ी नंबर भेजें
    await client.send_message(bot_entity, gadi_num)
    await asyncio.sleep(13) # डेटा फेच होने के लिए होल्ड करें
    
    # स्टेप 4: आखिरी रिस्पॉन्स प्राप्त करें
    final_msgs = await client.get_messages(bot_entity, limit=1)
    if final_msgs:
        return {"status": "success", "reply": final_msgs[0].text}
        
    return {"status": "error", "message": "बोट से कोई रिस्पॉन्स नहीं मिला।"}

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
