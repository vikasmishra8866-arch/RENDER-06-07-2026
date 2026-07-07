import os
import asyncio
import threading
import base64
from flask import Flask, request, jsonify, render_template_string

# --- परफेक्ट इवेंट लूप और थ्रेडिंग फिक्स ---
loop = asyncio.new_event_loop()

def start_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

from telethon import TelegramClient

app = Flask(__name__)

# Render Environment Variables
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
        <p>नीचे बटन दबाएं, फिर टेलीग्राम ऐप के Settings -> Devices -> Link Desktop Device में जाकर स्कैन करें।</p>
        <button onclick="generateQR()" class="btn-qr">1. QR कोड जेनरेट करें 🖼️</button>
        <br>
        <img id="qr_img" src="" alt="Telegram QR Code">
    </div>

    <hr style="border: 0; border-top: 1px solid #eee; margin: 25px 0;">

    <div>
        <h4 style="color: #27ae60; margin: 5px 0;">🔍 व्हीकल नंबर सर्च</h4>
        <input type="text" id="v_number" placeholder="GJ05MS9717" value="GJ05MS9717">
        <button onclick="searchVehicle()">ऑटो-क्लिक बोट रन करें 🚀</button>
    </div>

    <div id="status_box" class="status-box">स्थिति: तैयार है। यदि पहली बार चला रहे हैं तो पहले QR स्कैन करें।</div>
</div>

<script>
let box = document.getElementById('status_box');
let qrImg = document.getElementById('qr_img');
let checkInterval = null;

async function generateQR() {
    box.style.color = '#2f80ed';
    box.innerHTML = '⏳ टेलीग्राम सर्वर से QR कोड लाया जा रहा है... कृपया रुकें...';
    qrImg.style.display = 'none';
    
    try {
        let res = await fetch('/generate-qr', { method: 'POST' });
        let data = await res.json();
        
        if(data.status === 'qr_ready') {
            if(data.message === 'already_logged_in') {
                box.style.color = '#27ae60';
                box.innerHTML = '🎉 आप पहले से ही लॉग इन हैं! सीधे गाड़ी नंबर सर्च कर सकते हैं।';
                return;
            }
            qrImg.src = "data:image/png;base64," + data.image;
            qrImg.style.display = 'block';
            box.innerHTML = '✅ QR कोड तैयार है! अपने फोन के टेलीग्राम से इसे तुरंत स्कैन करें।';
            
            if(checkInterval) clearInterval(checkInterval);
            checkInterval = setInterval(checkLoginStatus, 3000);
        } else {
            box.style.color = '#c0392b';
            box.innerHTML = '❌ एरर: ' + data.message;
        }
    } catch (e) {
        box.style.color = '#c0392b';
        box.innerHTML = '❌ सर्वर से कनेक्ट करने में दिक्कत आ रही है।';
    }
}

async function checkLoginStatus() {
    try {
        let res = await fetch('/check-qr-status');
        let data = await res.json();
        if(data.status === 'logged_in') {
            clearInterval(checkInterval);
            qrImg.style.display = 'none';
            box.style.color = '#27ae60';
            box.innerHTML = '🎉 टेलीग्राम सफलतापूर्वक लिंक हो गया है! अब आप गाड़ी सर्च कर सकते हैं।';
        } else if (data.status === 'expired') {
            clearInterval(checkInterval);
            qrImg.style.display = 'none';
            box.style.color = '#c0392b';
            box.innerHTML = '❌ QR कोड की समय सीमा समाप्त हो गई। कृपया दोबारा बटन दबाएं।';
        }
    } catch(e) {}
}

async function searchVehicle() {
    let num = document.getElementById('v_number').value.trim();
    if(!num) return alert('कृपया गाड़ी नंबर डालें!');
    box.style.color = '#d35400';
    box.innerHTML = '⏳ बोट पर ऑटो-क्लिक बटन दबाया जा रहा है और गाड़ी नंबर सेंड हो रहा है... (15 सेकंड रुकें)...';
    
    try {
        let res = await fetch('/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_number: num })
        });
        let data = await res.json();
        if(data.status === 'success') {
            box.style.color = '#2c3e50';
            box.innerHTML = '✅ <b>बोट से प्राप्त गाड़ी की डिटेल्स:</b>\\n\\n' + data.reply;
        } else {
            box.style.color = '#c0392b';
            box.innerHTML = '❌ <b>सर्च एरर:</b> ' + data.message;
        }
    } catch (e) {
        box.style.color = '#c0392b';
        box.innerHTML = '❌ रिक्वेस्ट फेल हो गई। सर्वर लॉग्स चेक करें।';
    }
}
</script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

async def _async_qr_flow():
    if not client.is_connected():
        await client.connect()
    
    if await client.is_user_authorized():
        return {"already_logged_in": True}

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

async def _async_check_qr():
    token = qr_state.get("token")
    if not token:
        if await client.is_user_authorized():
            return "logged_in"
        return "expired"
    try:
        await token.wait(timeout=1)
        return "logged_in"
    except asyncio.TimeoutError:
        return "waiting"
    except Exception:
        return "expired"

@app.route('/check-qr-status')
def check_qr_status():
    try:
        future = asyncio.run_coroutine_threadsafe(_async_check_qr(), loop)
        res = future.result()
        return jsonify({"status": res})
    except Exception:
        return jsonify({"status": "waiting"})

# --- [बड़ा अपडेट]: बोट के नए बटन 'Vehicle Details + Contact' को हैंडल करने का परफेक्ट फ्लो ---
async def _execute_bot_flow(gadi_num):
    if not client.is_connected():
        await client.connect()
    
    if not await client.is_user_authorized():
        return {"status": "error", "message": "टेलीग्राम लिंक नहीं है। पहले ऊपर QR कोड जनरेट करके स्कैन करें।"}
    
    bot_entity = await client.get_input_entity(BOT_USERNAME)
    
    # 1. सबसे पहले बोट को फ्रेश /start भेजेंगे
    await client.send_message(bot_entity, "/start")
    await asyncio.sleep(3) # बोट के रिस्पॉन्स का वेट करेंगे
    
    button_text_to_send = None
    
    # 2. बोट के मैसेज में आए इनलाइन बटन्स चेक करेंगे
    messages = await client.get_messages(bot_entity, limit=1)
    if messages:
        message = messages[0]
        if message.reply_markup and hasattr(message.reply_markup, 'rows'):
            for row in message.reply_markup.rows:
                for button in row.buttons:
                    # 'vehicle' शब्द को ढूंढेंगे (ताकि 'Vehicle Details + Contact' मैच हो जाए)
                    if "vehicle" in button.text.lower():
                        button_text_to_send = button.text
                        break
                if button_text_to_send: break

    # अगर इनलाइन बटन रिप्लाई नहीं कर रहा, तो सीधे टेक्स्ट मैसेज के रूप में भेजेंगे
    if not button_text_to_send:
        button_text_to_send = "🚘 Vehicle Details + Contact"

    # 3. सही बटन टेक्स्ट बोट को भेजें
    await client.send_message(bot_entity, button_text_to_send)
    await asyncio.sleep(3) # बोट को प्रोसेस करने का टाइम दें
    
    # 4. अब गाड़ी नंबर भेजें
    await client.send_message(bot_entity, gadi_num)
    await asyncio.sleep(12) # बोट रिस्पॉन्स के लिए 12 सेकंड होल्ड करें
    
    # 5. बोट का फाइनल रिस्पॉन्स निकालें
    final_messages = await client.get_messages(bot_entity, limit=1)
    if final_messages:
        return {"status": "success", "reply": final_messages[0].text}
        
    return {"status": "error", "message": "बोट से गाड़ी का विवरण प्राप्त नहीं हो सका।"}

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
