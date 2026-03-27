from flask import Flask
import os
from routes.user import user_bp
from flask_cors import CORS
from dotenv import load_dotenv
from routes.auth import auth

# โหลดตัวแปรจาก .env (ตอนนี้จะมีแค่ข้อมูลของ GraphDB)
load_dotenv()

app = Flask(__name__)

# Secret Key สำหรับการทำ Session ของ Flask (จำเป็นต้องมีเพื่อให้ Login ได้)
app.secret_key = "secret1234" 

# เปิดใช้งาน CORS (Cross-Origin Resource Sharing)
CORS(app)

# ลงทะเบียน Blueprint (เชื่อมโยง Route ต่างๆ เข้ากับตัวแอป)
app.register_blueprint(auth)
app.register_blueprint(user_bp, url_prefix='/user')

if __name__ == '__main__':
    # รันเซิร์ฟเวอร์
    print("🚀 Starting Flask Server (Powered by GraphDB Semantic Web)...")
    app.run(debug=True, port=5000)