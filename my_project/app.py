import os
import asyncio
import threading
from flask import Flask, request, jsonify
from telethon import TelegramClient

app = Flask(__name__)

# Render Environment Variables से चाबियां उठाना
API_ID = int(os.getenv("TG_API_ID", "30587359"))
API_HASH = os.getenv("TG_API_HASH", "841b57b9782c258672af34c5f7146f56")
BOT_USERNAME = os.getenv("TARGET_BOT_USERNAME", "@rtovehicleinfoobot")

# Async Loop को बैकग्राउंड में सेट करना (टेलीग्राम के लिए जरूरी है)
loop = asyncio.new_event_loop()
def start_loop(loop_env):
    asyncio.set_event_loop(loop_env)
    loop_env.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

# बिना किसी फाइल झंझट के टेलीग्राम क्लाइंट (Memory Session)
client = TelegramClient(None, API_ID, API_HASH, loop=loop)

@app.route('/')
def home():
    # सीधे स्क्रीन पर गाड़ी नंबर डालने का सुंदर इंटरफ़ेस
    return """
    <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif; max-width: 500px; margin-left: auto; margin-right: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: #2c3e50;">🚗 Parivahan Service Bot Tester</h2>
        <p style="color: #7f8c8d;">यहाँ गाड़ी नंबर डालकर चेक करें कि टेलीग्राम बोट काम कर रहा है या नहीं।</p>
        
        <div style="margin-top: 30px;">
            <input type="text" id="v_number" placeholder="UP32XX1234" style="width: 80%; padding: 10px; font-size: 16px; border: 2px solid #3498db; border-radius: 5px; text-transform: uppercase;">
            <br><br>
            <button onclick="testBot()" style="background-color: #27ae60; color: white; border: none; padding: 10px 20px; font-size: 16px; border-radius: 5px; cursor: pointer; width: 85%;">बोट टेस्ट करें 🚀</button>
        </div>
        
        <div id="result_box" style="margin-top: 30px; padding: 15px; border-radius: 5px; font-weight: bold; background-color: #f8f9fa; min-height: 40px; word-wrap: break-word; text-align: left;">
            स्टेटस: बोट टेस्ट करने के लिए तैयार है।
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
        box.innerHTML = '⏳ टेलीग्राम बोट से कनेक्ट हो रहा है... कृपया 5 से 15 सेकंड रुकें...';
        
        try {
            let response = await fetch('/test-bot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vehicle_number: num })
            });
            let data = await response.json();
            
            if(data.status === "success") {
                box.style.color = '#27ae60';
                box.innerHTML = '✅ <b>बोट काम कर रहा है!</b><br><br><b>बोट का जवाब:</b><br>' + data.reply.replace(/\\n/g, '<br>');
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
        
        # बोट को गाड़ी नंबर भेजना
        await client.send_message(BOT_USERNAME, gadi_num)
        
        # बोट के जवाब का 12 सेकंड तक इंतज़ार करना
        await asyncio.sleep(12)
        
        # बोट चैट से आखिरी मैसेज उठाना
        async for message in client.iter_messages(BOT_USERNAME, limit=1):
            return {"status": "success", "reply": message.text}
            
        return {"status": "error", "message": "बोट की तरफ से कोई जवाब नहीं मिला।"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/test-bot', methods=['POST'])
def test_bot_route():
    gadi_number = request.json.get('vehicle_number', '').strip().upper()
    # बैकग्राउंड थ्रेड में टेलीग्राम फंक्शन चलाना ताकि फ्लैस्क क्रैश न हो
    future = asyncio.run_coroutine_threadsafe(send_and_recv(gadi_number), loop)
    return jsonify(future.result())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
