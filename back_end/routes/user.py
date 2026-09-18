from datetime import datetime, timedelta
from flask import Blueprint, json, render_template, jsonify, request, session, redirect, url_for
import calendar
from werkzeug.security import check_password_hash, generate_password_hash

from modules.db.patient_repository import  process_patient_streak_on_complete, get_patient_streak
from modules.db.plan_repository import update_schedule_status
from utils.security import login_required  # 🛡️ ยามเฝ้าประตูสำหรับผู้ใช้ทั่วไป

from modules.logic import process_patient_realtime
from modules.db import (
    save_raw_patient_data, get_all_recommendations, get_patient_latest_record,
    get_all_exercises_for_library, get_exercise_details_by_id, get_exercise_by_id,
    generate_30_days_plan, get_dashboard_schedule, delete_user_schedule,
    update_daily_plan_status, get_daily_plan_info,
    get_password_hash_by_id, update_user_profile_db
)
from modules.ocr_service import process_ocr_image

user_bp = Blueprint('user', __name__)


@user_bp.route('/dashboard')
@login_required
def dashboard_page():
    user_id = session['user_id']
    print("🔍 DEBUG user_id ที่ล็อกอินอยู่ตอนนี้คือ:", user_id)

    thai_months = [
        "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
        "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
    ]
    today = datetime.now().date()
    current_date_info = {
        "day": today.day,
        "month_name": thai_months[today.month - 1],
        "year": today.year + 543,
        "today_date": today
    }

    # ดึงตาราง 30 วันจาก GraphDB
    raw_schedule = get_dashboard_schedule(user_id)

    schedule_data = []
    for r in raw_schedule:
        actual_date = r["date_obj"]
        short_month_name = thai_months[actual_date.month - 1][:3] + "."

        current_status = r["status"]
        
        # 🟢 ถ้าเป็นวันในอดีต + ต้องออกกำลังกาย + ยังไม่ได้กดทำ + สถานะเดิมยังไม่ใช่ "Missed"
        if actual_date < today and r["is_exercise_day"] and not r["completed"] and current_status != "Missed":
            current_status = "Missed"
            
            # 🔥 สั่งบันทึกสถานะ "Missed" ลง GraphDB ทันที
            try:
                update_schedule_status(r["id"], "Missed")
                print(f"✅ Updated status to Missed in GraphDB for plan: {r['id']}")
            except Exception as e:
                print(f"❌ Error updating GraphDB: {e}")

        schedule_data.append({
            'id': r["id"],
            'day_of_week': r["day_of_week"],
            'is_exercise_day': r["is_exercise_day"],
            'exercise_name': r["exercise_name"],
            'completed': r["completed"],
            'duration_minutes': r["duration_minutes"],
            'date_num': actual_date.day,
            'month_index': actual_date.month - 1,
            'year': actual_date.year,
            'display_date': f"{actual_date.day} {short_month_name}",
            'is_today': (actual_date == today),
            'status': current_status,
        })

    # 2. 🔥 เพิ่มการดึงข้อมูล Streak จาก GraphDB
    streak_info = get_patient_streak(user_id)

    # 3. 🔥 ส่ง streak_info ไปยังหน้า HTML template (user/index.html)
    return render_template(
        'user/index.html', 
        schedule=schedule_data, 
        info=current_date_info,
        streak_info=streak_info  # <--- เพิ่มจุดนี้
    )

@user_bp.route('/recommendations')
@login_required
def user_recommendations():
    return render_template('user/rec_1.html')


@user_bp.route('/exercises')
@login_required
def user_exercise():
    exercises_data = get_all_exercises_for_library()
    return render_template('user/exercise.html', exercises=exercises_data)


@user_bp.route('/exercise-detail/<ex_id>')
@login_required
def exercise_detail(ex_id):
    ex = get_exercise_by_id(ex_id)
    if not ex:
        return "ไม่พบข้อมูลท่าออกกำลังกายนี้", 404
    return render_template('user/detail.html', ex=ex)


@user_bp.route('/knowledge')
@login_required
def user_knowledge():
    return render_template('user/extraknowledge.html')


@user_bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "ไม่มีข้อมูลส่งมา"}), 400

    # ✅ แก้ IDOR: บังคับใช้ ID ของคนที่ล็อกอินอยู่เท่านั้น
    # ไม่เชื่อค่า data['id'] ที่ client ส่งมาเด็ดขาด ป้องกันการยัดข้อมูลให้คนไข้คนอื่น
    data['id'] = session['user_id']

    save_raw_patient_data(data)
    recs, warns, comorbs, complis = process_patient_realtime(data['id'], input_data=data)
    return jsonify({"status": "ok", "exercises": recs, "warnings": warns, "comorbs": comorbs, "complis": complis})

@user_bp.route('/get_latest_checkup', methods=['GET'])
@login_required
def get_latest_data_api():
    data = get_patient_latest_record(session['user_id'])
    return jsonify(data)


@user_bp.route('/select_plan/<patient_id>')
@login_required
def select_plan_page(patient_id):
    # ✅ ตัดคำว่า "Patient" ออกก่อนนำมาเทียบกัน ป้องกันปัญหา String ไม่ตรงกัน
    clean_patient_id = str(patient_id).replace("Patient", "")
    clean_session_id = str(session['user_id']).replace("Patient", "")

    if clean_patient_id != clean_session_id:
        return "ไม่มีสิทธิ์เข้าถึงข้อมูลนี้", 403

    all_recs = get_all_recommendations(patient_id) # ยังคงส่งค่าดั้งเดิมไปหาข้อมูล
    return render_template('user/select_plan.html', patient_id=patient_id, exercises=all_recs)


@user_bp.route('/select_plan2/<patient_id>')
@login_required
def select_plan2_page(patient_id):
    clean_patient_id = str(patient_id).replace("Patient", "")
    clean_session_id = str(session['user_id']).replace("Patient", "")

    if clean_patient_id != clean_session_id:
        return "ไม่มีสิทธิ์เข้าถึงข้อมูลนี้", 403

    exercise_ids_str = request.args.get('exercises', '')
    exercise_ids = [ex.strip() for ex in exercise_ids_str.split(',') if ex.strip()]
    
    if not exercise_ids:
        return redirect(url_for('user.select_plan_page', patient_id=patient_id))

    selected_plans = []
    for ex_id in exercise_ids:
        # ลองเรียกฟังก์ชันที่มีอยู่ใน modules/db (ถ้า get_exercise_details_by_id ไม่ติด ให้ลอง get_exercise_by_id)
        plan_data = get_exercise_details_by_id(ex_id)
        if not plan_data:
            plan_data = get_exercise_by_id(ex_id)
            
        if plan_data:
            # ตรวจสอบ key ให้มี id ติดไปด้วย
            if isinstance(plan_data, dict) and 'id' not in plan_data:
                plan_data['id'] = ex_id
            selected_plans.append(plan_data)

    print("DEBUG selected_plans:", selected_plans)  # ดูค่าที่พิมพ์ออกมาใน Terminal

    # กำหนด plan ตัวแรกเพื่อไม่ให้หน้า template เดิมพัง
    first_plan = selected_plans[0] if selected_plans else None

    return render_template(
        'user/select_plan2.html',
        patient_id=patient_id,
        plans=selected_plans,
        plan=first_plan,  # ส่ง plan ตัวแรกไปด้วย
        exercise_ids_str=exercise_ids_str
    )


@user_bp.route('/save_schedule', methods=['POST'])
@login_required
def save_schedule():
    user_id = session['user_id']
    
    # ✅ เปลี่ยนมารับค่า exercise_ids แบบพหูพจน์ ที่รวบรวมรหัสทั้งหมดไว้
    exercise_ids_str = request.form.get('exercise_ids') 
    if not exercise_ids_str:
        return "Missing exercise selections", 400

    # แปลงจาก string "12025,17016" เป็น List ['12025', '17016']
    exercise_ids = [ex.strip() for ex in exercise_ids_str.split(',') if ex.strip()]

    exact_dates_str = request.form.getlist('exact_dates')
    if not exact_dates_str:
        return "Missing selected dates", 400

    exact_dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in exact_dates_str]
    daily_target_minutes = int(request.form.get('daily_target_minutes', 30))

    # ✅ ส่ง List ของ exercise_ids เข้าไปให้ฟังก์ชันสร้างตาราง (ต้องไปปรับฟังก์ชันรับค่าด้วย)
    success = generate_30_days_plan(user_id, exercise_ids, exact_dates, daily_target_minutes)

    if success:
        return redirect(url_for('user.dashboard_page'))
    else:
        return "Database error during schedule generation", 500


@user_bp.route('/update_day_status', methods=['POST'])
@login_required
def update_day_status():
    data = request.json
    day_node_id = data.get('day_id')
    completed = data.get('completed')
    duration = data.get('duration', 0)
    user_id = session.get('user_id')

    if not day_node_id:
        return jsonify({'status': 'error', 'message': 'Missing day_id'}), 400

    # ตรวจสอบสิทธิ์ IDOR
    expected_owner_fragment = f"Patient{user_id}_"
    if expected_owner_fragment not in day_node_id:
        return jsonify({'status': 'error', 'message': 'ไม่มีสิทธิ์เข้าถึงข้อมูลนี้'}), 403

    # 1. อัปเดตสถานะของวันนั้น
    success = update_daily_plan_status(day_node_id, completed, duration)

    if success:
        # 2. 🔥 ถ้าออกกำลังกายเสร็จสมบูรณ์ คำนวณและอัปเดต Streak
        if completed:
            streak_result = process_patient_streak_on_complete(user_id)

            return jsonify({
                'status': 'success',
                'streak_updated': True,
                'current_streak': streak_result['current_streak'],
                'max_streak': streak_result['max_streak'],
                'message': 'บันทึกสำเร็จ! เพิ่ม Streak แล้ว 🔥'
            })
        
        # กรณีอัปเดตสถานะอื่นๆ สำเร็จแต่ไม่ได้นับ Streak
        return jsonify({'status': 'success', 'streak_updated': False, 'message': 'อัปเดตสถานะเรียบร้อย'})

    return jsonify({'status': 'error', 'message': 'Failed to update'}), 500


@user_bp.route('/reset_plan', methods=['POST'])
@login_required
def reset_plan():
    success = delete_user_schedule(session['user_id'])
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error"}), 500


@user_bp.route('/start_exercise/<day_node_id>')
@login_required
def start_exercise(day_node_id):
    # ✅ แก้ IDOR: ตรวจว่า day_node_id เป็นของคนที่ล็อกอินอยู่จริง
    expected_owner_fragment = f"Patient{session['user_id']}_"
    if expected_owner_fragment not in day_node_id:
        return redirect(url_for('user.dashboard_page'))

    info = get_daily_plan_info(day_node_id)
    if info:
        return render_template('user/start_exercise.html',
                                exercise_name=info["exercise_name"],
                                day_id=day_node_id,
                                is_completed=info["completed"],
                                target_minutes=info["target_minutes"])
    return redirect(url_for('user.dashboard_page'))


@user_bp.route('/active_exercise/<day_node_id>')
@login_required
def active_exercise(day_node_id):
    # ✅ แก้ IDOR: ตรวจว่า day_node_id เป็นของคนที่ล็อกอินอยู่จริง
    expected_owner_fragment = f"Patient{session['user_id']}_"
    if expected_owner_fragment not in day_node_id:
        return redirect(url_for('user.dashboard_page'))

    info = get_daily_plan_info(day_node_id)
    if info:
# เพิ่มการส่งค่า exercise_id (สำหรับดึงรูป GIF) และ youtube_id (สำหรับวิดีโอ) 
        return render_template('user/active_exercise.html',
                                day_id=day_node_id,
                                exercise_id=info.get("exercise_id"),   
                                exercise_name=info["exercise_name"],
                                target_minutes=info["target_minutes"],
                                youtube_id=info.get("youtube_id")) 
    return redirect(url_for('user.dashboard_page'))


@user_bp.route('/settings')
@login_required
def setting():
    return render_template('user/user_setting.html')


@user_bp.route('/api/update_settings', methods=['POST'])
@login_required
def update_settings():
    user_id = session['user_id']
    data = request.json

    # เช็ก OTP
    user_otp = data.get('otp')
    saved_otp = session.get('register_otp')  # ดึง OTP ที่สร้างไว้ตอน request_otp ออกมาเทียบ

    if not saved_otp or user_otp != saved_otp:
        return jsonify({"status": "error", "message": "รหัส OTP ไม่ถูกต้อง หรือหมดเวลา"}), 400

    firstname = data.get('firstname', '').strip()
    lastname = data.get('lastname', '').strip()
    email = data.get('email', '').strip()  # ดึง email มาด้วยเผื่อใช้งาน
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    new_hash = None

    # ถ้ามีการพิมพ์รหัสผ่านใหม่มา แปลว่าต้องการเปลี่ยนรหัสผ่าน
    if new_password:
        if not old_password:
            return jsonify({"status": "error", "message": "กรุณากรอกรหัสผ่านเดิมเพื่อยืนยัน"}), 400

        current_hash = get_password_hash_by_id(user_id)
        # ตรวจสอบว่ารหัสเดิมพิมพ์ถูกไหม
        if not current_hash or not check_password_hash(current_hash, old_password):
            return jsonify({"status": "error", "message": "รหัสผ่านเดิมไม่ถูกต้อง"}), 400

        # เข้ารหัสผ่านใหม่
        new_hash = generate_password_hash(new_password)

    # สั่งอัปเดตลง GraphDB (ถ้ามีการอัปเดตอีเมลใน DB ด้วย อย่าลืมไปแก้ฟังก์ชันนี้ให้รับค่า email ด้วยนะครับ)
    success = update_user_profile_db(user_id, firstname, lastname, new_hash)

    if success:
        # ลบ OTP ทิ้งหลังจากการใช้งานสำเร็จ เพื่อความปลอดภัย
        session.pop('register_otp', None)
        session.pop('register_email', None)

        # อัปเดต Session ให้ข้อมูลหน้าเว็บเปลี่ยนตาม
        session['firstname'] = firstname
        session['lastname'] = lastname
        if email:
            session['email'] = email

        return jsonify({"status": "success", "message": "อัปเดตข้อมูลสำเร็จ"})
    else:
        return jsonify({"status": "error", "message": "เกิดข้อผิดพลาดในการบันทึกข้อมูล"}), 500


@user_bp.route('/api/ocr', methods=['POST'])
@login_required
def handle_ocr_api():
    # 1. ตรวจสอบว่าฝั่ง JavaScript ส่งไฟล์ภาพมาจริงไหม
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file"}), 400

    try:
        # 2. เรียกใช้งานฟังก์ชันแปลงรูปภาพที่คุณ Import มารันประมวลผล
        ocr_result = process_ocr_image(file)

        return jsonify({
            "success": True,
            "data": ocr_result
        })

    except Exception as e:
        print(f"OCR Backend Error: {str(e)}")
        return jsonify({"success": False, "message": "เกิดข้อผิดพลาดในการประมวลผลภาพถ่าย"}), 500