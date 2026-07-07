import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <div style="text-align: center; margin-top: 50px; font-family: Arial, sans-serif;">
        <h1 style="color: #2c3e50;">🚀 Parivahan Service Test Web Live!</h1>
        <p style="font-size: 18px; color: #27ae60;">विकास भाई, बधाई हो! आपकी वेबसाइट रेंडर पर सफलता पूर्वक काम कर रही है।</p>
        <p style="color: #7f8c8d;">अब इसके बाद हम इसमें लॉगिन और टेलीग्राम सर्विस जोड़ेंगे।</p>
    </div>
    """

if __name__ == '__main__':
    # रेंडर के पोर्ट पर चलने के लिए फिक्स
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
