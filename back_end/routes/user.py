from flask import Blueprint, render_template, jsonify, request
from modules.logic import process_patient_realtime
from modules.database import save_raw_patient_data # สมมติว่ามีฟังก์ชันนี้

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
def user_dashboard():
    return render_template('user/index.html')

@user_bp.route('/recommendations')
def user_recommendations():
    return render_template('user/rec_1.html')

@user_bp.route('/exercises')
def user_exercise():
    return render_template('user/exercise.html')

@user_bp.route('/knowledge')
def user_knowledge():
    return render_template('user/extraknowledge.html')

@user_bp.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    # 1. บันทึกข้อมูลดิบก่อน
    save_raw_patient_data(data)
    # 2. ประมวลผลและได้ผลลัพธ์
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