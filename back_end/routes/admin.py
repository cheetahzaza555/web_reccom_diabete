from flask import Blueprint, redirect, render_template, jsonify, request ,session, url_for
from utils.security import admin_required # เรียกยามมาใช้
from modules.database import delete_patient, get_patient_profile # สมมติว่ามีฟังก์ชันนี้
from modules.admin import get_admin_dashboard_stats, get_all_patients_management, get_recent_registered_users ,update_user_role_in_graphdb

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
    
@admin_bp.route("/update-role", methods=["POST"])
def update_user_role():
    # 🛡️ 1. ตรวจสอบระดับการเข้าถึงของแอดมินก่อน
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 403
        
    # 📦 2. แกะแกนข้อมูลที่หน้าบ้านส่งมาผ่าน JSON
    data = request.get_json()
    user_id = data.get("user_id")
    new_role = data.get("new_role")
    
    if not user_id or not new_role:
        return jsonify({"success": False, "message": "ข้อมูลที่ได้รับไม่ครบถ้วน"}), 400
        
    # 🔄 3. เรียกใช้งานฟังก์ชันแยกที่เราสร้างไว้เพื่อเปลี่ยนข้อมูลในคลังข้อมูล
    success, message = update_user_role_in_graphdb(user_id, new_role)
    
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": f"หลังบ้านขัดข้อง: {message}"}), 500