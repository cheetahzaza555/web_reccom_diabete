from flask import Flask
import datetime
import os
from routes.user import user_bp
from flask_cors import CORS
from dotenv import load_dotenv
from routes.auth import auth
from routes.admin import admin_bp
from apscheduler.schedulers.background import BackgroundScheduler
from modules.db.reschedule_repository import run_daily_reschedule_job ,get_all_patients_with_active_plan, reschedule_missed_days
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
    print("⏳ บังคับรันระบบเลื่อนตาราง (โหมดจำลองข้ามเวลา)...")
    
    # หลอกระบบว่าวันนี้คืออีก 3 วันข้างหน้า (บวกเพิ่ม 3 วัน)
    fake_today = datetime.datetime.today().date() + datetime.timedelta(days=1)
    print(f"🕒 จำลองเวลาปัจจุบันเป็น: {fake_today}")

    # ดึงรายชื่อคนไข้และสั่งรันทีละคน โดยโยนเวลาจำลองเข้าไป
    patient_ids = get_all_patients_with_active_plan()
    for pid in patient_ids:
        try:
            changed = reschedule_missed_days(pid, today=fake_today)
            if changed:
                print(f"[reschedule] เลื่อนตารางให้ Patient{pid} เรียบร้อย (โหมดจำลอง)")
        except Exception as e:
            print(f"[reschedule] เกิดข้อผิดพลาดกับ Patient{pid}: {e}")

    return f"สั่งจำลองการข้ามเวลาไปยังวันที่ {fake_today} เรียบร้อย! ลองรีเฟรชหน้าเว็บดูครับ"

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