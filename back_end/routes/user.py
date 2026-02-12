from flask import Blueprint, render_template, jsonify, request, session
from modules.logic import process_patient_realtime
from modules.database import save_raw_patient_data, get_all_recommendations , get_patient_latest_record, get_all_exercises_for_library
from modules.database import get_exercise_details_by_id


user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
def user_dashboard():
    return render_template('user/index.html')

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