from flask import Flask
import os
from routes.user import user_bp
from flask_cors import CORS
from dotenv import load_dotenv
from routes.auth import auth
from routes.admin import admin_bp
from apscheduler.schedulers.background import BackgroundScheduler
from modules.db.reschedule_repository import run_daily_reschedule_job
from routes.webhook import webhook_bp
from modules.line_utils import run_morning_reminder_job # 🌟 นำเข้าหุ่นยนต์แจ้งเตือนที่เพิ่งจัดระเบียบใหม่

# โหลดตัวแปรจาก .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# 🤖 รวมการตั้งเวลาหุ่นยนต์ทั้งหมดไว้ตรงนี้
scheduler = BackgroundScheduler(timezone="Asia/Bangkok")
scheduler.add_job(run_daily_reschedule_job, 'cron', hour=0, minute=5) # เลื่อนตารางตอนเที่ยงคืน
scheduler.add_job(run_morning_reminder_job, 'cron', hour=8, minute=0) # แจ้งเตือนตอน 8 โมงเช้า

if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    scheduler.start()

@app.route('/force-run-reschedule')
def force_run_reschedule():
    print("⏳ บังคับรันระบบเลื่อนตาราง (Manual Trigger)...")
    run_daily_reschedule_job()
    return "สั่งรันระบบเลื่อนตารางแล้ว! กรุณาเช็กข้อความใน Terminal/Console ครับ"

@app.route('/force-run-reminder')
def force_run_reminder():
    print("⏳ บังคับรันระบบแจ้งเตือนทาง LINE...")
    run_morning_reminder_job()
    return "สั่งรันระบบแจ้งเตือนแล้ว! เช็กที่มือถือ หรือ Terminal ได้เลยครับ"

# เปิดใช้งาน CORS
CORS(app)

# ลงทะเบียน Blueprint
app.register_blueprint(auth)
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(webhook_bp, url_prefix='/line')

if __name__ == '__main__':
    print("🚀 Starting Flask Server (Powered by GraphDB Semantic Web)...")
    app.run(debug=True, port=5000)