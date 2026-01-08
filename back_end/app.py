# app.py
from flask import Flask, request, jsonify, render_template
from modules.database import get_patient_profile, delete_patient, save_raw_patient_data
from modules.logic import process_patient_realtime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
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

@app.route('/api/patient/<id>', methods=['GET'])
def get_patient(id):
    profile = get_patient_profile(id)
    if profile: 
        return jsonify({"status": "ok", **profile})
    return jsonify({"status": "error"})

@app.route('/api/reprocess/<id>', methods=['POST'])
def reprocess(id):
    process_patient_realtime(id)
    return jsonify({"status": "ok"})

@app.route('/api/delete/<id>', methods=['DELETE'])
def delete_pt(id):
    delete_patient(id)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)