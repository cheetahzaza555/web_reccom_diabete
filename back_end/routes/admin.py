from flask import Blueprint, redirect, render_template, jsonify, request, session, url_for
from modules.db.admin_repository import delete_avoidance, delete_category_from_ontology, delete_exercise_from_ontology, delete_frequency, delete_warning, get_all_categories_for_dropdown, get_all_categories_from_ontology, get_avoidance_page, get_frequencies, insert_exercise_to_ontology, insert_exercise_to_ontology_v2, save_or_update_avoidance, save_or_update_avoidance, save_or_update_frequency, save_or_update_warning, update_category_hierarchy_in_ontology, get_patient_warning
from modules.db.auth_repository import get_password_hash_by_id, update_user_profile_db
from modules.db.exercise_repository import get_all_exercises_for_library
from modules.db.swrl import *
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
@admin_required 
def exercises_management_page():
    return render_template(
        "admin/exercises.html",
        username=session.get("username"),
        role=session.get("role"),
        exercises=get_all_exercises_for_library(),
        categories=get_all_categories_for_dropdown()
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

@admin_bp.route('/category', methods=['GET'])
@admin_required
def categories_page():
    # ดึงข้อมูลหมวดหมู่จริงจาก GraphDB
    categories_data = get_all_categories_from_ontology()
    return render_template('admin/edit_category.html', categories=categories_data)

@admin_bp.route('/api/category/update', methods=['POST'])
@admin_required
def api_update_category_hierarchy():
    """API Endpoint สำหรับแก้ไข/อัปเดตสายตระกูลและชื่อหมวดหมู่"""
    try:
        data = request.get_json()
        
        category_id = data.get('category_id')          # เช่น "Walking"
        parent_category_id = data.get('parent_id')     # เช่น "Aerobic"
        label_th = data.get('label_th')                 # เช่น "การเดิน" (ส่งหรือไม่ส่งก็ได้)

        # Validation ตรวจสอบข้อมูลจำเป็น
        if not category_id or not parent_category_id:
            return jsonify({
                "success": False, 
                "message": "กรุณาระบุ category_id และ parent_id ให้ครบถ้วน"
            }), 400

        # เรียกใช้ฟังก์ชัน GraphDB ที่เราเตรียมไว้
        result = update_category_hierarchy_in_ontology(category_id, parent_category_id, label_th)

        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        print(f"❌ API Error: {e}")
        return jsonify({"success": False, "message": f"เกิดข้อผิดพลาดที่เซิร์ฟเวอร์: {str(e)}"}), 500

@admin_bp.route('/api/categories/delete', methods=['POST'])
@admin_required
def api_delete_category():
    data = request.json
    category_id = data.get('category_id')
    
    if not category_id:
        return jsonify({"success": False, "message": "ไม่พบ รหัสหมวดหมู่"}), 400

    success, message = delete_category_from_ontology(category_id)
    return jsonify({"success": success, "message": message})

@admin_bp.route('/frequencies', methods=['GET'])
@admin_required
def frequencies_page():
    frequencies = get_frequencies()
    return render_template('admin/frequency.html', frequencies=frequencies["data"])

@admin_bp.route('/api/frequency/update', methods=['POST'])
@admin_required
def api_save_or_update_frequency():
    data = request.json or {}
    
    freq_id = data.get('freq_id', '').strip()
    description = data.get('description', '').strip()

    # เช็คแค่ freq_id (เพราะไม่ใช้ label แล้ว)
    if not freq_id:
        return jsonify({
            "success": False, 
            "message": "กรุณากรอก Frequency ID"
        }), 400

    result = save_or_update_frequency(
        freq_id=freq_id,
        description=description
    )

    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 500
    
@admin_bp.route('/api/frequency/delete', methods=['DELETE', 'POST'])
@admin_required
def api_delete_frequency():
    data = request.json or {}
    
    freq_id = data.get('freq_id', '').strip()

    if not freq_id:
        return jsonify({
            "success": False, 
            "message": "กรุณาระบุ Frequency ID ที่ต้องการลบ"
        }), 400

    result = delete_frequency(freq_id=freq_id)

    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@admin_bp.route('/warning', methods=['GET'])
@admin_required
def warning_page():
    data = get_avoidance_page()
    return render_template('admin/warning_avoid.html', warnings=data["data"])

@admin_bp.route('/api/warning/update', methods=['POST'])
@admin_required
def api_update_warning():
    data = request.json or {}
    
    warning_id = data.get('id', '').strip()
    description = data.get('description', '').strip()

    if not warning_id:
        return jsonify({
            "success": False, 
            "message": "กรุณาระบุ Warning ID"
        }), 400

    result = save_or_update_avoidance(
        avoid_id=warning_id,
        description=description
    )

    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@admin_bp.route('/api/warning/delete', methods=['POST'])
@admin_required
def api_delete_warning():
    data = request.json or {}
        
    avoid_id = data.get('warning_id', '').strip()
    
    result = delete_avoidance(avoid_id=avoid_id)

    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@admin_bp.route('/patient_warning', methods=['GET'])
@admin_required
def patient_warnings_page():
    data = get_patient_warning()
    return render_template('admin/warning_patient.html', warnings=data["data"])

@admin_bp.route('/api/patient_warning/update', methods=['POST'])
@admin_required
def api_update_patient_warning():
    data = request.json or {}
    
    warning_id = data.get('id', '').strip()
    description = data.get('description', '').strip()

    if not warning_id:
        return jsonify({
            "success": False, 
            "message": "กรุณาระบุ Warning ID"
        }), 400

    result = save_or_update_warning(
        warning_id=warning_id,
        description=description
    )

    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 500


@admin_bp.route('/api/patient_warning/delete', methods=['POST'])
@admin_required
def api_delete_patient_warning():
    data = request.json or {}
        
    warning_id = data.get('warning_id', '').strip()
    
    result = delete_warning(warning_id=warning_id)

    if result.get("success"):
        return jsonify(result), 200
    else:
        return jsonify(result), 500

@admin_bp.route('/swrl', methods=['GET'])
@admin_required
def api_get_swrl_rules():
    """Endpoint สำหรับดึงกฎ SWRL ไปโชว์บนหน้าเว็บ Admin"""
    result = get_all_swrl_rules()
    if result["success"]:
        return render_template('admin/swrl.html', swrl_rules=result["data"]), 200
    return jsonify(result), 500

# 2. POST: เพิ่มกฎ SWRL ใหม่
@admin_bp.route('/api/swrl/rules/add', methods=['POST'])
@admin_required
def api_add_swrl_rule():
    data = request.get_json() or {}
    
    rule_label = data.get('rule_label')
    comment = data.get('comment', '')
    swrl_expression = data.get('swrl_expression')
    
    if not rule_label or not swrl_expression:
        return jsonify({"success": False, "message": "กรุณาระบุ rule_label และ swrl_expression"}), 400
        
    result = add_swrl_rule(
        rule_label=rule_label,
        comment=comment,
        swrl_expression=swrl_expression
    )
    
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


# 3. PUT: แก้ไขรายละเอียดกฎ SWRL
@admin_bp.route('/api/swrl/rules/update', methods=['PUT'])
@admin_required
def api_update_swrl_rule():
    data = request.get_json() or {}
    
    rule_uri = data.get('rule_uri')
    rule_label = data.get('rule_label')
    comment = data.get('comment', '')
    swrl_expression = data.get('swrl_expression')
    is_enabled = data.get('is_enabled', 'true')
    
    if not rule_uri or not rule_label or not swrl_expression:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบถ้วน (ต้องการ rule_uri, rule_label, swrl_expression)"}), 400
        
    result = update_swrl_rule(
        rule_uri=rule_uri,
        rule_label=rule_label,
        comment=comment,
        swrl_expression=swrl_expression,
        is_enabled=is_enabled
    )
    
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


# 4. DELETE: ลบกฎ SWRL
@admin_bp.route('/api/swrl/rules/delete', methods=['DELETE'])
@admin_required
def api_delete_swrl_rule():
    # รองรับทั้ง Query Param (?rule_uri=...) และ JSON Body
    rule_uri = request.args.get('rule_uri') or (request.get_json() or {}).get('rule_uri')
    
    if not rule_uri:
        return jsonify({"success": False, "message": "กรุณาระบุ rule_uri ที่ต้องการลบ"}), 400
        
    result = delete_swrl_rule(rule_uri=rule_uri)
    
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


# 5. PATCH: สลับสถานะเปิด/ปิดการใช้งานกฎ
@admin_bp.route('/api/swrl/rules/toggle', methods=['PATCH'])
@admin_required
def api_toggle_swrl_rule_status():
    data = request.get_json() or {}
    
    # ดึงค่าได้ทั้งจาก Query String หรือ JSON Body
    rule_uri = request.args.get('rule_uri') or data.get('rule_uri')
    is_enabled = request.args.get('is_enabled') if request.args.get('is_enabled') is not None else data.get('is_enabled')
    
    if not rule_uri or is_enabled is None:
        return jsonify({"success": False, "message": "กรุณาระบุ rule_uri และ status is_enabled"}), 400
        
    result = toggle_swrl_rule_status(rule_uri=rule_uri, is_enabled=is_enabled)
    
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code

