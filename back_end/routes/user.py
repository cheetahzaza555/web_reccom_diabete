from datetime import datetime, timedelta
from modules.auth_db import get_db_connection
from flask import Blueprint, json, render_template, jsonify, request, session, redirect, url_for
from modules.logic import process_patient_realtime
from modules.database import save_raw_patient_data, get_all_recommendations , get_patient_latest_record, get_all_exercises_for_library
from modules.database import get_exercise_details_by_id, get_exercise_by_id
import calendar

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
        # ✅ 1. เพิ่ม d.duration_minutes เข้าไปใน SQL
        sql_query = """
            SELECT 
                d.id, 
                d.day_of_week, 
                d.is_exercise_day, 
                d.exercise_name, 
                d.completed,
                d.duration_minutes, 
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
                # ✅ 2. เปลี่ยนจาก r[5] เป็น r[6] เพราะมี duration_minutes มาแทรกตรงกลาง
                week_start = r[6] 
                day_offset = r[1]
                actual_date = week_start + timedelta(days=day_offset)
                
                short_month_name = thai_months[actual_date.month - 1][:3] + "."
                display_date = f"{actual_date.day} {short_month_name}"

                schedule_data.append({
                    'id': r[0],
                    'day_of_week': r[1],
                    'is_exercise_day': r[2],
                    'exercise_name': r[3],
                    'completed': r[4],
                    'duration_minutes': r[5] if r[5] else 0, # ✅ 3. ดึงเวลาออกมาใส่ในตัวแปร
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

    return render_template('user/index.html', schedule=schedule_data, info=current_date_info)

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
    # 1. ใช้ฟังก์ชันใหม่ที่เราเพิ่งเขียน (ดึงข้อมูลตรงจาก GraphDB)
    # ฟังก์ชันนี้จะคืนค่าทั้ง ข้อมูลพื้นฐาน, steps และ precaution มาให้ในก้อนเดียวเลย
    ex = get_exercise_by_id(ex_id)
    
    # 2. ตรวจสอบว่ามีข้อมูลหรือไม่
    if not ex:
        return "ไม่พบข้อมูลท่าออกกำลังกายนี้", 404

    # 3. ส่งข้อมูล 'ex' ไปที่หน้า HTML ได้ทันที
    # ตอนนี้ ex จะมี ex['steps'] เป็น list และ ex['precaution'] เป็น string ตามที่ดึงมาจาก Graph
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

    username = session['username']
    patient_id = request.form.get('patient_id')
    exercise_name = request.form.get('exercise_name')
    
    # 1. รับค่าวันที่จิ้มในปฏิทิน
    exact_dates_str = request.form.getlist('exact_dates')
    if not exact_dates_str:
        return "Missing selected dates", 400

    exact_dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in exact_dates_str]
    
    # 2. วันที่เริ่มตาราง คือ "วันนี้" เสมอ ตามที่ UI กำหนดกรอบ 30 วัน
    start_date = datetime.today().date()
    
    daily_target = request.form.get('daily_target_minutes')
    daily_target_minutes = int(daily_target) if daily_target else 30

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_row = cur.fetchone()
        if not user_row:
            return "User not found", 404
        user_id = user_row[0]

        current_month_plan_id = None
        current_month = None
        current_year = None
        current_week_plan_id = None
        
        # ✅ 3. บังคับลูป 30 วัน (เพื่อครอบคลุม 1 เดือน ข้ามเดือนได้สบาย)
        for i in range(30):
            current_date = start_date + timedelta(days=i)
            
            # เช็คและสร้าง monthly_plan หากเปลี่ยนเดือน
            if current_date.month != current_month or current_date.year != current_year:
                current_month = current_date.month
                current_year = current_date.year
                
                cur.execute("""
                    INSERT INTO monthly_plan (user_id, month, year) 
                    VALUES (%s, %s, %s) RETURNING id
                """, (user_id, current_month, current_year))
                current_month_plan_id = cur.fetchone()[0]
            
            # เช็คและสร้าง weekly_plan (ทำทุกๆ 7 วัน)
            if i % 7 == 0:
                cur.execute("""
                    INSERT INTO weekly_plan (monthly_plan_id, start_date) 
                    VALUES (%s, %s) RETURNING id
                """, (current_month_plan_id, current_date))
                current_week_plan_id = cur.fetchone()[0]

            # ✅ 4. เช็คว่าวันที่กำลังเซฟ ตรงกับวันที่ผู้ใช้จิ้มเลือกไว้หรือไม่
            is_exercise = current_date in exact_dates 
            
            day_exercise_name = exercise_name if is_exercise else None
            day_target_minutes = daily_target_minutes if is_exercise else 0
            
            # บันทึกข้อมูล
            cur.execute("""
                INSERT INTO days_plan (weekly_plan, day_of_week, is_exercise_day, exercise_name, completed, target_minutes) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                current_week_plan_id, 
                i % 7, 
                is_exercise, 
                day_exercise_name, 
                False,
                day_target_minutes 
            ))

        conn.commit()
        return redirect(url_for('user.dashboard_page'))

    except Exception as e:
        conn.rollback()
        print(f"Error generating automatic schedule: {e}")
        return f"Database error: {e}", 500
    finally:
        cur.close()
        conn.close()

@user_bp.route('/update_day_status', methods=['POST'])
def update_day_status():
    data = request.json
    day_id = data.get('day_id')
    completed = data.get('completed')
    duration = data.get('duration', 0) # ✅ รับเวลามาด้วย (ถ้าไม่มีให้เป็น 0)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # ✅ สั่งอัปเดตทั้งสถานะการทำ และเวลาลงใน Database
        cur.execute("""
            UPDATE days_plan 
            SET completed = %s, duration_minutes = %s 
            WHERE id = %s
        """, (completed, duration, day_id))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
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

@user_bp.route('/start_exercise/<int:day_id>')
def start_exercise(day_id):
    # เช็คว่าล็อกอินหรือยัง
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # ✅ 1. เพิ่ม target_minutes เข้าไปในคำสั่ง SQL
        cur.execute("SELECT exercise_name, completed, target_minutes FROM days_plan WHERE id = %s", (day_id,))
        row = cur.fetchone()
        
        if row:
            exercise_name = row[0]
            is_completed = row[1]
            # ✅ 2. ดึงเวลาเป้าหมายออกมา (ถ้าดึงมาแล้วเป็น None ให้ตั้งค่าเริ่มต้นเป็น 30 กันเหนียวไว้)
            target_minutes = row[2] if row[2] else 30
            
            # ✅ 3. ส่ง target_minutes ไปให้หน้า HTML ด้วย
            return render_template('user/start_exercise.html', 
                                   exercise_name=exercise_name,
                                   day_id=day_id,
                                   is_completed=is_completed,
                                   target_minutes=target_minutes)
        else:
            print("ไม่พบข้อมูลตารางออกกำลังกาย")
            return redirect(url_for('user.dashboard_page'))
            
    except Exception as e:
        print(f"Error loading start exercise: {e}")
        return redirect(url_for('user.dashboard_page'))
        
    finally:
        cur.close()
        conn.close()

@user_bp.route('/active_exercise/<int:day_id>')
def active_exercise(day_id):
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # ✅ 1. เพิ่มการดึง target_minutes จากฐานข้อมูล
        cur.execute("SELECT exercise_name, target_minutes FROM days_plan WHERE id = %s", (day_id,))
        row = cur.fetchone()
        
        if row:
            exercise_name = row[0]
            # ✅ 2. ดึงเวลาออกมา (ถ้าไม่มีให้ตั้งเป็น 30 ไว้ก่อน)
            target_minutes = row[1] if row[1] else 30
            
            # ✅ 3. ส่ง target_minutes ไปให้หน้า HTML
            return render_template('user/active_exercise.html', 
                                   day_id=day_id, 
                                   exercise_name=exercise_name,
                                   target_minutes=target_minutes)
        else:
            return redirect(url_for('user.dashboard_page'))
            
    except Exception as e:
        print(f"Error loading active exercise: {e}")
        return redirect(url_for('user.dashboard_page'))
        
    finally:
        cur.close()
        conn.close()