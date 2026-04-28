from datetime import datetime, timedelta
from flask import Blueprint, json, render_template, jsonify, request, session, redirect, url_for
import calendar

# ✅ เปลี่ยนมา Import ฟังก์ชันจาก database.py แทน
from modules.logic import process_patient_realtime
from modules.database import (
    save_raw_patient_data, get_all_recommendations, get_patient_latest_record, 
    get_all_exercises_for_library, get_exercise_details_by_id, get_exercise_by_id,
    generate_30_days_plan, get_dashboard_schedule, delete_user_schedule,
    update_daily_plan_status, get_daily_plan_info
)

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
def dashboard_page():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    
    user_id = session['user_id']
    
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

    # ✅ ดึงตาราง 30 วันจาก GraphDB
    raw_schedule = get_dashboard_schedule(user_id)
    
    schedule_data = []
    for r in raw_schedule:
        actual_date = r["date_obj"]
        short_month_name = thai_months[actual_date.month - 1][:3] + "."
        
        schedule_data.append({
            'id': r["id"], # จะเป็น DailyPlan_Patient...
            'day_of_week': r["day_of_week"],
            'is_exercise_day': r["is_exercise_day"],
            'exercise_name': r["exercise_name"],
            'completed': r["completed"],
            'duration_minutes': r["duration_minutes"],
            'date_num': actual_date.day,
            'month_index': actual_date.month - 1, 
            'year': actual_date.year,
            'display_date': f"{actual_date.day} {short_month_name}", 
            'is_today': (actual_date == today)
        })

    return render_template('user/index.html', schedule=schedule_data, info=current_date_info)

@user_bp.route('/recommendations')
def user_recommendations():
    return render_template('user/rec_1.html')

@user_bp.route('/exercises')
def user_exercise():
    exercises_data = get_all_exercises_for_library()
    return render_template('user/exercise.html', exercises=exercises_data)

@user_bp.route('/exercise-detail/<ex_id>')
def exercise_detail(ex_id):
    ex = get_exercise_by_id(ex_id)
    if not ex: return "ไม่พบข้อมูลท่าออกกำลังกายนี้", 404
    return render_template('user/detail.html', ex=ex)

@user_bp.route('/knowledge')
def user_knowledge():
    return render_template('user/extraknowledge.html')

@user_bp.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    save_raw_patient_data(data)
    recs, warns, comorbs, complis = process_patient_realtime(data['id'], input_data=data)
    return jsonify({"status": "ok", "exercises": recs, "warnings": warns, "comorbs": comorbs, "complis": complis})

@user_bp.route('/reprocess/<id>', methods=['POST'])
def reprocess(id):
    process_patient_realtime(id)
    return jsonify({"status": "ok"})

@user_bp.route('/get_latest_checkup', methods=['GET'])
def get_latest_data_api():
    if 'user_id' not in session: return jsonify({"found": False, "message": "Not logged in"})
    data = get_patient_latest_record(session['user_id'])
    return jsonify(data)

@user_bp.route('/select_plan/<patient_id>')  
def select_plan_page(patient_id):
    all_recs = get_all_recommendations(patient_id)
    return render_template('user/select_plan.html', patient_id=patient_id, exercises=all_recs)

@user_bp.route('/select_plan2/<patient_id>/<exercise_id>')
def select_plan2_page(patient_id, exercise_id):
    exercise_info = get_exercise_details_by_id(exercise_id)
    return render_template('user/select_plan2.html', patient_id=patient_id, plan=exercise_info)

@user_bp.route('/save_schedule', methods=['POST'])
def save_schedule():
    if 'user_id' not in session: return redirect(url_for('auth.login_page'))
    
    user_id = session['user_id']
    exercise_id = request.form.get('exercise_id') # แนะนำให้เปลี่ยนใน HTML ให้ส่ง id ท่ามาด้วย
    
    exact_dates_str = request.form.getlist('exact_dates')
    if not exact_dates_str: return "Missing selected dates", 400

    exact_dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in exact_dates_str]
    daily_target_minutes = int(request.form.get('daily_target_minutes', 30))

    # ✅ สร้างตาราง 30 วันด้วย GraphDB
    success = generate_30_days_plan(user_id, exercise_id, exact_dates, daily_target_minutes)
    
    if success: return redirect(url_for('user.dashboard_page'))
    else: return "Database error during schedule generation", 500

@user_bp.route('/update_day_status', methods=['POST'])
def update_day_status():
    data = request.json
    day_node_id = data.get('day_id')
    completed = data.get('completed')
    duration = data.get('duration', 0)

    # ✅ อัปเดต GraphDB
    success = update_daily_plan_status(day_node_id, completed, duration)
    
    if success: return jsonify({'status': 'success'})
    else: return jsonify({'status': 'error', 'message': 'Failed to update'}), 500

@user_bp.route('/reset_plan', methods=['POST'])
def reset_plan():
    if 'user_id' not in session: return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    success = delete_user_schedule(session['user_id'])
    if success: return jsonify({"status": "success"})
    else: return jsonify({"status": "error"}), 500

@user_bp.route('/start_exercise/<day_node_id>') # ✅ เปลี่ยน type เป็น string เพราะมันคือชื่อ Node ใน GraphDB
def start_exercise(day_node_id):
    if 'user_id' not in session: return redirect(url_for('auth.login_page'))
    
    info = get_daily_plan_info(day_node_id)
    if info:
        return render_template('user/start_exercise.html', 
                               exercise_name=info["exercise_name"],
                               day_id=day_node_id,
                               is_completed=info["completed"],
                               target_minutes=info["target_minutes"])
    return redirect(url_for('user.dashboard_page'))

@user_bp.route('/active_exercise/<day_node_id>')
def active_exercise(day_node_id):
    if 'user_id' not in session: return redirect(url_for('auth.login_page'))
    
    info = get_daily_plan_info(day_node_id)
    if info:
        return render_template('user/active_exercise.html', 
                               day_id=day_node_id, 
                               exercise_name=info["exercise_name"],
                               target_minutes=info["target_minutes"])
    return redirect(url_for('user.dashboard_page'))