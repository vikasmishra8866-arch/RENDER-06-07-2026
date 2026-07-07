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

from telethon import TelegramClient, events

app = Flask(__name__)

# Render Environment Variables
API_ID = int(os.getenv("TG_API_ID", "30587359"))
API_HASH = os.getenv("TG_API_HASH", "841b57b9782c258672af34c5f7146f56")
BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "@rtovehicleinfoobot")

def start_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()
client = TelegramClient(None, API_ID, API_HASH, loop=loop)

@app.route('/')
def home():
    return """
    <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; max-width: 500px; margin-left: auto; margin-right: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: #2c3e50;">🚗 Parivahan Service Auto-Clicker Live</h2>
        <p style="color: #7f8c8d;">यह कोड 'Vehicle Details + Contact' बटन दबाकर डिटेल्स निकालेगा।</p>
        
        <div style="margin-top: 30px;">
            <input type="text" id="v_number" placeholder="GJ05BY2328" style="width: 80%; padding: 10px; font-size: 16px; border: 2px solid #3498db; border-radius: 5px; text-transform: uppercase;">
            <br><br>
            <button onclick="testBot()" style="background-color: #27ae60; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 5px; cursor: pointer; width: 85%;">डिटेल्स निकालें 🚀</button>
        </div>
        
        <div id="result_box" style="margin-top: 30px; padding: 15px; border-radius: 5px; font-weight: bold; background-color: #f8f9fa; min-height: 40px; word-wrap: break-word; text-align: left;">
            स्टेटस: बोट पर बटन क्लिक टेस्ट करने के लिए तैयार है।
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
        box.innerHTML = '⏳ बोट को जगाया जा रहा है और "Vehicle Details" बटन पर क्लिक किया जा रहा है...';
        
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
        
        # १. बोट को /start भेजकर ताज़ा मेनू और बटन लोड करें
        await client.send_message(BOT_USERNAME, "/start")
        await asyncio.sleep(3) # बोट का रिस्पॉन्स और कीबोर्ड बटन आने का इंतज़ार
        
        button_clicked = False
        
        # २. बोट चैट के आख़िरी मैसेज में कीबोर्ड या इनलाइन बटन ढूंढना
        async for message in client.iter_messages(BOT_USERNAME, limit=1):
            # बोट के नीचे दिखने वाले रिप्लाई कीबोर्ड बटन्स को चेक करें
            if message.reply_markup and hasattr(message.reply_markup, 'rows'):
                for row in message.reply_markup.rows:
                    for button in row.buttons:
                        # बटन के टेक्स्ट में 'vehicle' नाम खोजें (जैसे: 🚗 Vehicle Details + Contact)
                        if "vehicle" in button.text.lower():
                            # सीधे उसी टेक्स्ट मैसेज को चैट में भेजकर बटन क्लिक को सिमुलेट करें
                            await client.send_message(BOT_USERNAME, button.text)
                            button_clicked = True
                            break
                    if button_clicked: break

        if not button_clicked:
            return {"status": "error", "message": "बोट के अंदर 'Vehicle Details' बटन नहीं मिल पाया। कृपया चेक करें कि बोट चालू है या नहीं।"}
            
        await asyncio.sleep(3) # "enter vehicle number" वाले मैसेज का इंतज़ार
        
        # ३. अब गाड़ी नंबर भेजें
        await client.send_message(BOT_USERNAME, gadi_num)
        
        # ४. ₹5 कटने और बोट द्वारा गाड़ी की असली डिटेल्स भेजने के लिए थोड़ा ज़्यादा (12 सेकंड) इंतज़ार करें
        await asyncio.sleep(12)
        
        # ५. फाइनल रिस्पॉन्स खींचें
        async for message in client.iter_messages(BOT_USERNAME, limit=1):
            return {"status": "success", "reply": message.text}
            
        return {"status": "error", "message": "गाड़ी नंबर भेजने के बाद बोट शांत रहा।"}
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
