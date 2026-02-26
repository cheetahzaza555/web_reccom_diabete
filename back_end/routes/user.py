from datetime import datetime, timedelta
from modules.auth_db import get_db_connection
from flask import Blueprint, json, render_template, jsonify, request, session, redirect, url_for
from modules.logic import process_patient_realtime
from modules.database import save_raw_patient_data, get_all_recommendations , get_patient_latest_record, get_all_exercises_for_library
from modules.database import get_exercise_details_by_id, get_exercise_by_id, EXERCISE_KNOWLEDGE, EXERCISE_VIDEOS

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

@user_bp.route('/exercise-detail/<ex_id>')
def exercise_detail(ex_id):
    # 1. ดึงข้อมูลจากคลัง (ดึง ID, รูป และหมวดหมู่จาก Ontology มาให้แล้ว)
    all_exercises = get_all_exercises_for_library()
    ex = next((item for item in all_exercises if item['id'] == ex_id), None)
    
    if not ex:
        return "ไม่พบข้อมูล", 404
    
    # 2. ดึง YouTube ID รายท่า (สำคัญ: ต้องแน่ใจว่า import EXERCISE_VIDEOS มาจาก database.py)
    # หากไม่เจอ ID ของท่านั้นๆ จะใช้คลิปกลาง (dQw4w9WgXcQ) เป็นค่าเริ่มต้น
    ex['youtube_id'] = EXERCISE_VIDEOS.get(ex_id)

    # 3. Logic เลือกชุดคำสอน (Steps) ตามหมวดหมู่จริงใน Ontology
    categories = ex.get('all_categories', [])
    
    if "StretchingExercise" in categories:
        info = EXERCISE_KNOWLEDGE["StretchingExercise"]
    elif any(c in categories for c in ["Resistance", "WeightBearingResistanceExercise", "NonWeightBearingResistanceExercise"]):
        info = EXERCISE_KNOWLEDGE["Resistance"]
    else:
        # สำหรับ Aerobic, Bicycling, WaterActivity หรือหมวดหมู่อื่นๆ
        info = EXERCISE_KNOWLEDGE.get("Aerobic", EXERCISE_KNOWLEDGE["StretchingExercise"]) 
    
    # 4. รวมข้อมูล "วิธีปฏิบัติ" และ "ข้อควรระวัง" เข้าไปในตัวแปร ex
    # เพื่อให้ HTML เรียกใช้ {{ ex.steps }} และ {{ ex.precaution }} ได้โดยไม่ Error
    ex['steps'] = info['steps']
    ex['precaution'] = info['precaution']

    # 5. ส่ง ex ไปที่หน้า HTML
    return render_template('user/detail.html', ex=ex)

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

@user_bp.route('/save_schedule', methods=['POST'])
def save_schedule():
    if 'username' not in session:
        return redirect(url_for('login_page'))

    data = request.form
    exercise_name = data.get('exercise_name')
    
    # 1. รับ JSON List ของวันที่ที่ User จิ้มมา
    selected_dates_json = data.get('selected_dates_json')
    
    try:
        # แปลง JSON String กลับเป็น Python List
        # ตัวอย่าง: ['2026-02-18', '2026-02-20', '2026-02-22']
        selected_dates_list = json.loads(selected_dates_json)
    except:
        return "Error parsing dates", 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        current_username = session['username']
        cur.execute("SELECT id FROM users WHERE username = %s", (current_username,))
        user = cur.fetchone()
        
        if not user: return "User not found", 404
        user_db_id = user[0] 

        # เราต้องวนลูปตาม "วันที่ที่ User เลือกมา" แทนการวนลูป 30 วัน
        # แต่เพื่อความสมบูรณ์ของโครงสร้าง DB (Monthly -> Weekly -> Days)
        # เราควรสร้าง Monthly/Weekly ให้ครบก่อน แล้วค่อย Insert Day
        
        # เรียงวันที่จากน้อยไปมาก
        selected_dates_list.sort()
        
        # แปลง string เป็น date object
        date_objects = [datetime.strptime(d, '%Y-%m-%d').date() for d in selected_dates_list]
        
        if not date_objects:
            return "No dates selected", 400

        # ใช้ Loop เดิม เพื่อสร้างโครงสร้างพื้นฐาน (Monthly/Weekly) ให้ครบ
        # แต่ตอน Insert Day ให้เช็คว่า "วันนี้มีใน list ที่ user เลือกไหม"
        
        start_date = date_objects[0]
        # สร้างเผื่อไปเลย 1 เดือน (30 วัน) นับจากวันแรกที่เลือก
        end_date = start_date + timedelta(days=30) 
        
        current_date = start_date

        while current_date < end_date:
            year = current_date.year
            month = current_date.month

            # --- A. Monthly Plan ---
            cur.execute("SELECT id FROM monthly_plan WHERE user_id = %s AND year = %s AND month = %s", (user_db_id, year, month))
            month_row = cur.fetchone()
            if month_row:
                monthly_id = month_row[0]
            else:
                cur.execute("INSERT INTO monthly_plan (user_id, year, month) VALUES (%s, %s, %s) RETURNING id", (user_db_id, year, month))
                monthly_id = cur.fetchone()[0]

            # --- B. Weekly Plan ---
            week_num = current_date.isocalendar()[1]
            week_start = current_date - timedelta(days=current_date.weekday())

            cur.execute("SELECT id FROM weekly_plan WHERE monthly_plan_id = %s AND week_number = %s", (monthly_id, week_num))
            week_row = cur.fetchone()
            if week_row:
                weekly_id = week_row[0]
            else:
                cur.execute("INSERT INTO weekly_plan (monthly_plan_id, week_number, start_date) VALUES (%s, %s, %s) RETURNING id", (monthly_id, week_num, week_start))
                weekly_id = cur.fetchone()[0]

            # --- C. Days Plan ---
            for i in range(7):
                day_date = week_start + timedelta(days=i)
                
                # เช็คว่าวันนี้อยู่ในช่วงเวลาที่เราสนใจไหม
                if start_date <= day_date < end_date:
                    
                    # ✅ CHECKPOINT: วันนี้ user เลือกมาหรือเปล่า?
                    # แปลง day_date เป็น string เพื่อเทียบกับ list ที่ส่งมา
                    date_str = day_date.strftime('%Y-%m-%d')
                    is_exercise = True if date_str in selected_dates_list else False
                    
                    cur.execute("SELECT id FROM days_plan WHERE weekly_plan = %s AND day_of_week = %s", (weekly_id, day_date.weekday()))
                    if not cur.fetchone():
                        cur.execute("""
                            INSERT INTO days_plan (day_of_week, weekly_plan, is_exercise_day, exercise_name, completed)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            day_date.weekday(),
                            weekly_id,
                            is_exercise, # True ถ้า user จิ้ม, False ถ้าไม่จิ้ม
                            exercise_name if is_exercise else "พักผ่อน",
                            False
                        ))

            current_date += timedelta(weeks=1)
            current_date = current_date - timedelta(days=current_date.weekday())

        conn.commit()
        return redirect(url_for('user.dashboard_page'))

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return f"Database Error: {e}", 500
    finally:
        cur.close()
        conn.close()

@user_bp.route('/update_day_status', methods=['POST'])
def update_day_status():
    data = request.json
    day_id = data.get('day_id')
    completed = data.get('completed')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE days_plan 
            SET completed = %s 
            WHERE id = %s
        """, (completed, day_id))
        conn.commit()
        return {"status": "success"}
    
    except Exception as e:
        print(f"Error: {e}")
        return "Database Error", 500
    finally:
        cur.close()
        conn.close()

@user_bp.route('/reset_plan', methods=['POST'])
def reset_plan():
    # 1. เช็ค Login
    if 'username' not in session:
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    username = session['username']
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 2. หา User ID
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        user_id = user[0]

        # 3. ลบข้อมูล (ต้องลบจากลูกไปหาแม่: วัน -> สัปดาห์ -> เดือน)
        
        # ลบ Days Plan (รายวัน)
        cur.execute("""
            DELETE FROM days_plan
            WHERE weekly_plan IN (
                SELECT id FROM weekly_plan
                WHERE monthly_plan_id IN (
                    SELECT id FROM monthly_plan WHERE user_id = %s
                )
            )
        """, (user_id,))

        # ลบ Weekly Plan (รายสัปดาห์)
        cur.execute("""
            DELETE FROM weekly_plan
            WHERE monthly_plan_id IN (
                SELECT id FROM monthly_plan WHERE user_id = %s
            )
        """, (user_id,))

        # ลบ Monthly Plan (รายเดือน)
        cur.execute("DELETE FROM monthly_plan WHERE user_id = %s", (user_id,))

        conn.commit()
        print(f"🗑️ Plan reset successfully for user: {username}")
        return jsonify({"status": "success"})

    except Exception as e:
        conn.rollback()
        print(f"❌ Error resetting plan: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()