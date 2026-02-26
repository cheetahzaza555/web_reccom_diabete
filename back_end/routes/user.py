from datetime import datetime, timedelta
from modules.auth_db import get_db_connection
from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for
from modules.logic import process_patient_realtime
from modules.database import save_raw_patient_data, get_all_recommendations , get_patient_latest_record, get_all_exercises_for_library
from modules.database import get_exercise_details_by_id, get_exercise_by_id, EXERCISE_KNOWLEDGE


user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
def dashboard_page():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    username = session['username']
    conn = get_db_connection()
    cur = conn.cursor()
    
    schedule_data = []
    
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

    try:
        # ✅ แก้ไข SQL Query: ลบเงื่อนไข m.month และ m.year ออก เพื่อดึงข้อมูลแผนทั้งหมด
        sql_query = """
            SELECT 
                d.id, 
                d.day_of_week, 
                d.is_exercise_day, 
                d.exercise_name, 
                d.completed,
                w.start_date
            FROM days_plan d
            JOIN weekly_plan w ON d.weekly_plan = w.id
            JOIN monthly_plan m ON w.monthly_plan_id = m.id
            JOIN users u ON m.user_id = u.id
            WHERE u.username = %s 
            ORDER BY w.start_date ASC, d.day_of_week ASC
        """
        
        cur.execute(sql_query, (username,))
        rows = cur.fetchall()
        
        if rows:
            for r in rows:
                week_start = r[5]
                day_offset = r[1]
                actual_date = week_start + timedelta(days=day_offset)
                
                # ✅ ลบเงื่อนไข `if actual_date.month == today.month:` ออก
                # เพื่อให้เพิ่มข้อมูลทุกวันลงในตาราง ไม่ว่าจะอยู่เดือนไหน
                
                # รูปแบบวันที่แบบสั้นๆ (เช่น "25 ก.พ.") เพื่อให้ดูง่ายถ้าข้ามเดือน
                short_month_name = thai_months[actual_date.month - 1][:3] + "."
                display_date = f"{actual_date.day} {short_month_name}"

                schedule_data.append({
                    'id': r[0],
                    'day_of_week': r[1],
                    'is_exercise_day': r[2],
                    'exercise_name': r[3],
                    'completed': r[4],
                    'date_num': actual_date.day,
                    'month_index': actual_date.month - 1, 
                    'year': actual_date.year,
                    'display_date': display_date, 
                    'is_today': (actual_date == today)
                })

    except Exception as e:
        print(f"Error fetching dashboard: {e}")
    finally:
        cur.close()
        conn.close()

    return render_template('user/index.html', 
                        schedule=schedule_data, 
                        info=current_date_info)

@user_bp.route('/recommendations')
def user_recommendations():
    return render_template('user/rec_1.html')

@user_bp.route('/exercises')
def user_exercise():
    # 1. ดึงข้อมูลทั้งหมดจาก GraphDB
    exercises_data = get_all_exercises_for_library()
    
    # 2. ส่งข้อมูลไปที่หน้า HTML (ตัวแปรชื่อ exercises)
    return render_template('user/exercise.html', exercises=exercises_data)

@user_bp.route('/knowledge')
def user_knowledge():
    return render_template('user/extraknowledge.html')

@user_bp.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    save_raw_patient_data(data)
    recs, warns, comorbs, complis = process_patient_realtime(data['id'], input_data=data)
    
    return jsonify({
        "status": "ok",
        "exercises": recs,
        "warnings": warns,
        "comorbs": comorbs,
        "complis": complis
    })

@user_bp.route('/reprocess/<id>', methods=['POST'])
def reprocess(id):
    process_patient_realtime(id)
    return jsonify({"status": "ok"})

@user_bp.route('/get_latest_checkup', methods=['GET'])
def get_latest_data_api():
    # 1. เช็คว่าล็อกอินหรือยัง
    if 'user_id' not in session:
        return jsonify({"found": False, "message": "Not logged in"})
        
    # 2. ดึง ID ของคนที่ล็อกอินอยู่ (สำคัญมาก! จุดนี้คือตัวแก้ปัญหาข้อมูลผิดคน)
    current_user_id = session['user_id'] 
    
    print(f"🔍 Fetching data for User ID: {current_user_id}") # (Optional) สั่งปริ้นเช็คใน Terminal

    # 3. เรียกฟังก์ชันเทพที่คุณเพิ่งเขียน (ส่ง ID เข้าไป)
    # *** ตรงนี้แหละครับที่เชื่อมต่อกัน ***
    data = get_patient_latest_record(current_user_id)
    
    # 4. ส่งผลลัพธ์กลับไปให้หน้าเว็บ (JavaScript)
    return jsonify(data)



@user_bp.route('/select_plan/<patient_id>')  
def select_plan_page(patient_id):
    
    # 1. เรียกใช้ฟังก์ชันจาก database.py ที่คุณเพิ่งแก้
    # มันจะคืนค่าเป็น list ของ dict เช่น [{'id': '12025', 'name': 'วิ่ง...', 'met': '7.0', ...}]
    all_recs = get_all_recommendations(patient_id)
    
    # 2. ส่งตัวแปร exercises (ที่เป็น list of dicts) ไปให้หน้าเว็บ
    return render_template('user/select_plan.html', patient_id=patient_id, exercises=all_recs)

@user_bp.route('/save_selection', methods=['POST'])
def save_selection_route():
    try:
        # รับข้อมูล JSON จากหน้าเว็บ
        data = request.json
        patient_id = data.get('patient_id')
        exercise_id = data.get('exercise_id')
        
        print(f"📥 Received save request: {patient_id} chose {exercise_id}")

        # เรียกฟังก์ชันบันทึกลง DB
        if save_patient_selection(patient_id, exercise_id):
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Database Save Failed'}), 500

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@user_bp.route('/select_plan2/<patient_id>/<exercise_id>')
def select_plan2_page(patient_id, exercise_id):
    
    # 1. ดึงรายละเอียดของท่าที่เลือกมาโชว์
    exercise_info = get_exercise_details_by_id(exercise_id)
    
    # 2. ส่งข้อมูลไปที่หน้าเว็บ
    return render_template('user/select_plan2.html', 
                        patient_id=patient_id, 
                        plan=exercise_info)
    
@user_bp.route('/exercise-detail/<ex_id>')
def exercise_detail(ex_id):
    # 1. Query ดึงข้อมูลพื้นฐานจาก GraphDB เหมือนเดิม
    exercise_data = get_exercise_by_id(ex_id) # ฟังก์ชันสมมติที่ดึงชื่อและหมวดหมู่มา
    
    # 2. Logic เลือกข้อมูลฟิกค่า
    cat = exercise_data['original_type'] # เช่น StretchingExercise
    
    # ดึงค่าความรู้ตามหมวดหมู่ (ถ้าไม่เจอให้ใช้ค่า Aerobic เป็นพื้นฐาน)
    knowledge = EXERCISE_KNOWLEDGE.get(cat)
    if not knowledge:
        # ถ้าเป็นพวก Walking, Running ให้ใช้กลุ่ม Aerobic
        knowledge = EXERCISE_KNOWLEDGE.get("Aerobic")
        
    return render_template('user/detail.html', ex=exercise_data, info=knowledge)