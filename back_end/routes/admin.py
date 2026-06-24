from flask import Blueprint, redirect, render_template, jsonify ,session, url_for
from utils.security import admin_required # เรียกยามมาใช้
from modules.database import delete_patient, get_patient_profile # สมมติว่ามีฟังก์ชันนี้
from modules.admin import get_admin_dashboard_stats, get_all_patients_management, get_recent_registered_users

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/patient/<id>', methods=['GET'])
def get_patient(id):
    profile = get_patient_profile(id)
    if profile: 
        return jsonify({"status": "ok", **profile})
    return jsonify({"status": "error"})


@admin_bp.route('/api/patient/<id>', methods=['DELETE'])
def delete_patient_route(id):
    result = delete_patient(id)
    if result:
        return jsonify({"status": "deleted"})
    return jsonify({"status": "error"})

@admin_bp.route("/dashboard")
def dashboard_page():
    # 🛡️ ระบบความปลอดภัย: เช็คสิทธิ์แอดมิน
    if "user_id" not in session or session.get("role") != "admin":
        print("🚨 [Admin Route Log] Access Denied: User is not admin or not logged in!")
        return redirect(url_for("auth.login_page"))
        
    print(f"👤 [Admin Route Log] Admin '{session.get('username')}' is accessing dashboard.")
    
    # 📊 เรียกดึงข้อมูลจริงจากคลังฐานข้อมูล GraphDB
    stats_data = get_admin_dashboard_stats()
    recent_users = get_recent_registered_users()
    
    # 🪵 PRINT LOG: ตรวจสอบข้อมูลก่อนโยนไป HTML
    print("====== 🪵 ADMIN DASHBOARD DEBUG LOG ====== ")
    print(f"📦 stats_dataที่ได้: {stats_data}")
    print(f"👥 recent_usersที่ได้: {recent_users}")
    print("===========================================")
    
    # ส่งค่าตัวแปรทั้งหมดเข้าไปแปะลงในหน้ากาก HTML
    return render_template(
        "admin/index.html",
        username=session.get("username"),
        role=session.get("role"),
        stats=stats_data,
        recent_users=recent_users
    )
    
@admin_bp.route("/users")
def users_management_page():
    # 🛡️ เช็คสิทธิ์แอดมิน
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("auth.login_page"))
        
    # ดึงรายชื่อคนไข้ทั้งหมด
    patients = get_all_patients_management()
    
    return render_template(
        "admin/users.html",  # เดี๋ยวเราจะสร้างไฟล์นี้กันครับ
        username=session.get("username"),
        role=session.get("role"),
        patients=patients
    )