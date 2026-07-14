from flask import Blueprint, redirect, render_template, jsonify, request, session, url_for
from modules.db.admin_repository import delete_exercise_from_ontology, insert_exercise_to_ontology, insert_exercise_to_ontology_v2
from modules.db.auth_repository import get_password_hash_by_id, update_user_profile_db
from modules.db.exercise_repository import get_all_exercises_for_library
from utils.security import admin_required  # 🛡️ เปิดใช้งานยามเฝ้าประตู
from werkzeug.security import check_password_hash, generate_password_hash
import random
from modules.db import (
    delete_patient,
    get_patient_profile,
    get_admin_dashboard_stats,
    get_all_users_with_roles,
    get_patient_health_summary,
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
# 🩺 API สำหรับ Admin ดูข้อมูลสุขภาพผู้ป่วย (bmi/fpg/type)
# ==========================================

@admin_bp.route('/api/patients/health-summary', methods=['GET'])
@admin_required  # 🔒 เฉพาะแอดมินเท่านั้นที่ดูข้อมูลสุขภาพผู้ป่วยทั้งหมดได้
def patients_health_summary():
    patients = get_patient_health_summary()
    return jsonify({"status": "ok", "patients": patients})


# ==========================================
# 📊 ฝั่งแสดงผลหน้ากากเว็บ (HTML Pages)
# ==========================================

@admin_bp.route("/dashboard")
@admin_required  # 🔒 ใช้ยามคุมแทนการเขียน if-else ซ้ำซ้อน
def dashboard_page():

    # 📊 เรียกดึงข้อมูลจริงจากคลังฐานข้อมูล GraphDB
    stats_data = get_admin_dashboard_stats()
    recent_users = get_recent_registered_users()

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
    # ดึงรายชื่อผู้ใช้ทั้งหมดพร้อมสิทธิ์ (role) สำหรับหน้าจัดการสิทธิ์
    patients = get_all_users_with_roles()

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
        role=session.get("role"),
        exercises=get_all_exercises_for_library()
    )       
    
@admin_bp.route('/exercises/add', methods=['POST'])
@admin_required
def add_exercise():
    try:
        # 1. ดึงข้อมูล JSON ที่ส่งมาจาก JavaScript (fetch)
        data = request.get_json()
        
        name = data.get('name')
        exercise_type = data.get('type')  # คลาสย่อยที่เลือกจาก Dropdown (เช่น Walking, Running)
        mets = data.get('mets')
        youtube_id = data.get('youtube_id')

        # ตรวจสอบค่าว่างเบื้องต้น
        if not name or not exercise_type or not mets:
            return jsonify({"success": False, "message": "กรุณากรอกข้อมูลให้ครบถ้วน"}), 400

        # 2. เรียกใช้ฟังก์ชันที่แยกไปอยู่อีกไฟล์นึงเพื่อจัดการระบบคลังความรู้
        result = insert_exercise_to_ontology(
            name=name,
            exercise_type=exercise_type,
            mets=mets,
            youtube_id=youtube_id
        )
        
        # 3. ส่งผลลัพธ์กลับไปยัง JavaScript หน้าบ้านตามที่ไฟล์ภายนอกตอบกลับมา
        if result.get("success"):
            return jsonify({"success": True, "message": result.get("message")})
        else:
            return jsonify({"success": False, "message": result.get("message")}), 400

    except Exception as e:
        print(f"Error adding exercise in admin route: {str(e)}")
        return jsonify({"success": False, "message": f"เกิดข้อผิดพลาดภายในเซิร์ฟเวอร์: {str(e)}"}), 500
    
@admin_bp.route('/exercises/delete/<exercise_id>', methods=['POST'])
@admin_required
def delete_exercise(exercise_id):
    result = delete_exercise_from_ontology(exercise_id)
    if result.get("success"):
        return jsonify({"success": True, "message": result.get("message")})
    else:
        return jsonify({"success": False, "message": result.get("message")}), 400

@admin_bp.route('/exercises/update', methods=['POST'])
@admin_required
def update_exercise():
    try:
        data = request.get_json()
        
        # ดึงข้อมูลที่หน้าบ้านส่งมาแก้ไข
        exercise_id = data.get('id')
        name = data.get('name')
        exercise_type = data.get('type')
        mets = data.get('mets')
        youtube_id = data.get('youtube_id')

        if not exercise_id or not name or not exercise_type or not mets:
            return jsonify({"success": False, "message": "กรุณากรอกข้อมูลให้ครบถ้วน"}), 400

        # 💡 หลักการแก้ไขของ Ontology (GraphDB) ที่ง่ายและปลอดภัยที่สุดคือ: 
        # 1. ลบความสัมพันธ์ (Triples) ของเก่าที่ผูกกับ ID นี้ออกทั้งหมดก่อน
        delete_exercise_from_ontology(exercise_id)
        
        # 2. บันทึกไตรภาคชุดใหม่ (8 แถวมาตรฐาน) เข้าไปแทนที่โดยใช้ ID เดิม
        # ปรับแก้ฟังก์ชัน insert_exercise_to_ontology เล็กน้อย (ตามข้อ 2 ด้านล่าง) ให้รับ ID เดิมไปเซฟซ้ำได้
        result = insert_exercise_to_ontology_v2(exercise_id, name, exercise_type, mets, youtube_id)

        if result.get("success"):
            return jsonify({"success": True, "message": "อัปเดตข้อมูลสำเร็จ"})
        else:
            return jsonify({"success": False, "message": result.get("message")}), 400

    except Exception as e:
        print(f"❌ Error updating exercise in route: {e}")
        return jsonify({"success": False, "message": f"เซิร์ฟเวอร์ขัดข้อง: {str(e)}"}), 500

@admin_bp.route('/settings')
@admin_required
def setting():
    return render_template('admin/admin_setting.html')

@admin_bp.route('/api/update_settings', methods=['POST'])
@admin_required
def update_admin_settings():
    admin_id = session.get('admin_id') or session.get('user_id')
    data = request.json

    firstname = data.get('firstname', '').strip()
    lastname = data.get('lastname', '').strip()
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    new_hash = None
    if new_password:
        if not old_password:
            return jsonify({"status": "error", "message": "กรุณากรอกรหัสผ่านปัจจุบันเพื่อยืนยัน"}), 400
        current_hash = get_password_hash_by_id(admin_id) # ⚠️ ตรวจสอบว่าฟังก์ชันนี้ใช้ของแอดมินด้วยหรือไม่
        if not current_hash or not check_password_hash(current_hash, old_password):
            return jsonify({"status": "error", "message": "รหัสผ่านปัจจุบันไม่ถูกต้อง"}), 400
        new_hash = generate_password_hash(new_password)

    #  แก้ไขตรงนี้: เปลี่ยนเป็นฟังก์ชันอัปเดตโปรไฟล์ของแอดมิน
    success = update_user_profile_db(admin_id, firstname, lastname, new_hash)

    if success:
        session['firstname'] = firstname
        session['lastname'] = lastname
        return jsonify({"status": "success", "message": "อัปเดตข้อมูลผู้ดูแลระบบสำเร็จ"})
    else:
        return jsonify({"status": "error", "message": "เกิดข้อผิดพลาดในการบันทึกข้อมูล"}), 500