from flask import Blueprint, redirect, render_template, jsonify, request, session, url_for
from utils.security import admin_required  # 🛡️ เปิดใช้งานยามเฝ้าประตู
from modules.database import delete_patient, get_patient_profile 
from modules.admin import (
    get_admin_dashboard_stats, 
    get_all_patients_management, 
    get_recent_registered_users, 
    update_user_role_in_graphdb
)

admin_bp = Blueprint('admin', __name__)

# ==========================================
# 🛑 ฝั่ง API สำหรับการเรียกดึง/ลบ ข้อมูลคนไข้
# ==========================================

@admin_bp.route('/api/patient/<id>', methods=['GET'])
@admin_required  # 🔒 ดักสิทธิ์: ถ้าไม่ล็อกอิน/ไม่ใช่แอดมิน จะโดนดีดออกทันที
def get_patient(id):
    profile = get_patient_profile(id)
    if profile: 
        return jsonify({"status": "ok", **profile})
    return jsonify({"status": "error", "message": "ไม่พบข้อมูลผู้ป่วย"})


@admin_bp.route('/api/patient/<id>', methods=['DELETE'])
@admin_required  # 🔒 ดักสิทธิ์: ป้องกันคนนอกแอบมายิง API ลบคนไข้
def delete_patient_route(id):
    result = delete_patient(id)
    if result:
        return jsonify({"status": "deleted"})
    return jsonify({"status": "error", "message": "ไม่สามารถลบข้อมูลได้"})


# ==========================================
# 📊 ฝั่งแสดงผลหน้ากากเว็บ (HTML Pages)
# ==========================================

@admin_bp.route("/dashboard")
@admin_required  # 🔒 ใช้ยามคุมแทนการเขียน if-else ซ้ำซ้อน
def dashboard_page():
    print(f"👤 [Admin Route Log] Admin '{session.get('username')}' is accessing dashboard.")
    
    # 📊 เรียกดึงข้อมูลจริงจากคลังฐานข้อมูล GraphDB
    stats_data = get_admin_dashboard_stats()
    recent_users = get_recent_registered_users()
    
    # 🪵 PRINT LOG: ตรวจสอบข้อมูลก่อนโยนไป HTML
    print("====== 🪵 ADMIN DASHBOARD DEBUG LOG ====== ")
    print(f"📦 stats_data ที่ได้: {stats_data}")
    print(f"👥 recent_users ที่ได้: {recent_users}")
    print("===========================================")
    
    return render_template(
        "admin/index.html",
        username=session.get("username"),
        role=session.get("role"),
        stats=stats_data,
        recent_users=recent_users
    )


@admin_bp.route("/users")
@admin_required  # 🔒 บล็อกถาวร พอล็อกเอาต์แล้วเปิดหน้านี้จะโดนเด้งกลับหน้าแรกทันที
def users_management_page():
    # ดึงรายชื่อคนไข้ทั้งหมด
    patients = get_all_patients_management()
    
    return render_template(
        "admin/users.html",
        username=session.get("username"),
        role=session.get("role"),
        patients=patients
    )


@admin_bp.route("/update-role", methods=["POST"])
@admin_required  # 🔒 ดักฝั่ง API เปลี่ยนสิทธิ์
def update_user_role():
    # 📦 แกะแกนข้อมูลที่หน้าบ้านส่งมาผ่าน JSON
    data = request.get_json()
    user_id = data.get("user_id")
    new_role = data.get("new_role")
    
    if not user_id or not new_role:
        return jsonify({"success": False, "message": "ข้อมูลที่ได้รับไม่ครบถ้วน"}), 400
        
    # 🔄 เรียกใช้งานฟังก์ชันแยกเพื่อเปลี่ยนข้อมูลในคลัง GraphDB
    success, message = update_user_role_in_graphdb(user_id, new_role)
    
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": f"หลังบ้านขัดข้อง: {message}"}), 500
    
@admin_bp.route("/exercises", methods=["GET"])
@admin_required  # 🔒 บล็อกถาวร พอล็อกเอาต์แล้วเปิดหน้านี้จะโดนเด้งกลับหน้าแรกทันที
def exercises_management_page():
    return render_template(
        "admin/exercises.html",
        username=session.get("username"),
        role=session.get("role")
    )       