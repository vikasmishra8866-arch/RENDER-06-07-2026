import os
import asyncio
import threading
from flask import Flask, request, jsonify

# --- इवेंट लूप फिक्स ---
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from telethon import TelegramClient
from telethon.tl.types import PeerUser

app = Flask(__name__)

# Render Environment Variables
API_ID = int(os.getenv("TG_API_ID", "30587359"))
API_HASH = os.getenv("TG_API_HASH", "841b57b9782c258672af34c5f7146f56")

# [बदलाव] यूजरनेम के झंझट से बचने के लिए सीधे बोट की न्यूमेरिकल Peer ID
# यह आईडी सीधे टेलीग्राम डेटाबेस से कनेक्ट होती है
BOT_ID = 5900593414 
bot_peer = PeerUser(user_id=BOT_ID)

def start_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()
client = TelegramClient(None, API_ID, API_HASH, loop=loop)

@app.route('/')
def home():
    return """
    <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; max-width: 500px; margin-left: auto; margin-right: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: #2c3e50;">🚗 Parivahan Service Auto-Clicker v3</h2>
        <p style="color: #7f8c8d;">यह कोड बोट आईडी का उपयोग करके सीधे डेटा निकालेगा।</p>
        
        <div style="margin-top: 30px;">
            <input type="text" id="v_number" placeholder="GJ05BY2328" style="width: 80%; padding: 10px; font-size: 16px; border: 2px solid #3498db; border-radius: 5px; text-transform: uppercase;">
            <br><br>
            <button onclick="testBot()" style="background-color: #27ae60; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 5px; cursor: pointer; width: 85%;">डिटेल्स निकालें 🚀</button>
        </div>
        
        <div id="result_box" style="margin-top: 30px; padding: 15px; border-radius: 5px; font-weight: bold; background-color: #f8f9fa; min-height: 40px; word-wrap: break-word; text-align: left;">
            स्टेटस: टेस्ट करने के लिए तैयार है।
        </div>
    </div>

    <script>
    async function testBot() {
        let num = document.getElementById('v_number').value.trim();
        if(!num) {
            alert('कृपया पहले गाड़ी नंबर डालें!');
            return;
        }
        
        let box = document.getElementById('result_box');
        box.style.color = '#d35400';
        box.innerHTML = '⏳ डायरेक्ट बोट आईडी से चैट सिंक की जा रही है... कृपया 10-15 सेकंड रुकें...';
        
        try {
            let response = await fetch('/test-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vehicle_number: num })
            });
            let data = await response.json();
            
            if(data.status === "success") {
                box.style.color = '#27ae60';
                box.innerHTML = '✅ <b>गाड़ी की जानकारी नीचे है:</b><br><br>' + data.reply.replace(/\\n/g, '<br>');
            } else {
                box.style.color = '#c0392b';
                box.innerHTML = '❌ <b>एरर:</b> ' + data.message;
            }
        } catch(err) {
            box.style.color = '#c0392b';
            box.innerHTML = '❌ सर्वर से कनेक्शन टूट गया!';
        }
    }
    </script>
    """

async def send_and_recv(gadi_num):
    try:
        if not client.is_connected():
            await client.connect()
        
        # १. बोट आईडी पर सीधे /start भेजना
        await client.send_message(bot_peer, "/start")
        await asyncio.sleep(3)
        
        button_clicked = False
        
        # २. कीबोर्ड बटन ढूंढकर उसपर एक्शन लेना
        async for message in client.iter_messages(bot_peer, limit=1):
            if message.reply_markup and hasattr(message.reply_markup, 'rows'):
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        if "vehicle" in button.text.lower():
                            await client.send_message(bot_peer, button.text)
                            button_clicked = True
                            break
                    if button_clicked: break

        if not button_clicked:
            return {"status": "error", "message": "बोट के अंदर 'Vehicle Details' बटन नहीं मिल पाया।"}
            
        await asyncio.sleep(3) # नंबर मांगने का इंतज़ार
        
        # ३. गाड़ी नंबर भेजना
        await client.send_message(bot_peer, gadi_num)
        
        # ४. डिटेल्स लोड होने का इंतज़ार
        await asyncio.sleep(12)
        
        # ५. फाइनल रिस्पॉन्स खींचना
        async for message in client.iter_messages(bot_peer, limit=1):
            return {"status": "success", "reply": message.text}
            
        return {"status": "error", "message": "गाड़ी नंबर भेजने के बाद बोट से कोई रिस्पॉन्स नहीं आया।"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/test-bot', methods=['POST'])
def test_bot_route():
    gadi_number = request.json.get('vehicle_number', '').strip().upper()
    future = asyncio.run_coroutine_threadsafe(send_and_recv(gadi_number), loop)
    return jsonify(future.result())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
