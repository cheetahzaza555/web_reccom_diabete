# app.py
from flask import Flask, render_template, request, jsonify
import services # <--- เรียกใช้ services ที่เราเขียนแยกไว้

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    try:
        # 1. เรียกฟังก์ชันนี้ฟังก์ชันเดียว (มันจะเพิ่มข้อมูล + รันกฎให้เอง)
        patient_id = services.add_new_patient(data)
        
        # 2. ดึงผลลัพธ์มาแสดง
        exercises, warnings = services.get_patient_results(patient_id)
        
        return jsonify({
            "status": "ok", 
            "exercises": exercises, 
            "warnings": warnings
        })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/patient/<id>', methods=['GET'])
def get_patient(id):
    # 1. ไปดึงข้อมูลส่วนตัว (Profile)
    profile = services.get_patient_profile(id)
    
    if not profile:
        return jsonify({"status": "error", "message": "User not found"}), 404
        
    # 2. ไปดึงคำแนะนำและคำเตือน (ใช้ฟังก์ชันเดิมที่มีอยู่แล้ว)
    # เราใช้ ID ที่ถูกต้องที่ return มาจาก profile['found_id'] (เช่น Patient_99)
    # แต่ต้องตัดคำว่า "Patient_" หรือ "Patient" ออก เพื่อส่งให้ get_patient_results
    # หรือแก้ get_patient_results ให้รับ full ID ก็ได้
    
    # วิธีง่ายสุด: ส่ง full ID ไปให้ services ดึงผล
    # (คุณต้องไปแก้ services.get_patient_results นิดหน่อยให้รองรับ ID เต็ม หรือทำตามนี้)
    
    real_id_name = profile['found_id'] # เช่น Patient_99
    
    # ดึงผล Recommendation
    # หมายเหตุ: ฟังก์ชัน get_patient_results เดิมของคุณรับ input มาแล้วเติม "ex:" ข้างหน้า
    # เราจึงเรียกใช้ได้เลยโดยส่งชื่อ ID ไป
    exercises, warnings = services.get_patient_results(real_id_name)

    return jsonify({
        "status": "ok",
        "info": profile,
        "exercises": exercises,
        "warnings": warnings
    })
    
@app.route('/api/delete/<id>', methods=['DELETE'])
def delete_patient(id):
    try:
        services.delete_patient_by_id(id)
        return jsonify({"status": "ok", "message": f"ลบผู้ป่วย ID {id} สำเร็จ"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)