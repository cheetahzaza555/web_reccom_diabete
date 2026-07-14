from flask import Flask
import os
from routes.user import user_bp
from flask_cors import CORS
from dotenv import load_dotenv
from routes.auth import auth
from routes.admin import admin_bp
from apscheduler.schedulers.background import BackgroundScheduler
from modules.db import run_daily_reschedule_job

# โหลดตัวแปรจาก .env (ตอนนี้จะมีแค่ข้อมูลของ GraphDB)
load_dotenv()

app = Flask(__name__)

# Secret Key สำหรับการทำ Session ของ Flask (จำเป็นต้องมีเพื่อให้ Login ได้)
app.secret_key = os.getenv("SECRET_KEY")

scheduler = BackgroundScheduler(timezone="Asia/Bangkok")
scheduler.add_job(run_daily_reschedule_job, 'cron', hour=0, minute=5)

if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    scheduler.start()

@app.route('/force-run-reschedule')
def force_run_reschedule():
    print("⏳ บังคับรันระบบเลื่อนตาราง (Manual Trigger)...")
    run_daily_reschedule_job()
    return "สั่งรันระบบเลื่อนตารางแล้ว! กรุณาเช็กข้อความใน Terminal/Console ครับ"


# เปิดใช้งาน CORS (Cross-Origin Resource Sharing)
CORS(app)

# ลงทะเบียน Blueprint (เชื่อมโยง Route ต่างๆ เข้ากับตัวแอป)
app.register_blueprint(auth)
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(admin_bp, url_prefix="/admin")

if __name__ == '__main__':
    # รันเซิร์ฟเวอร์
    print("🚀 Starting Flask Server (Powered by GraphDB Semantic Web)...")
    app.run(debug=True, port=5000)