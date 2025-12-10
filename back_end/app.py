from flask import Flask, render_template, jsonify, request
import services

app = Flask(__name__)

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    try:
        # 1. บันทึกลง DB (ทำไปเถอะ เพื่อเก็บประวัติ)
        services.save_raw_patient_data(data)
        
        # 2. คำนวณผล (แก้บรรทัดนี้!!!)
        
        # ❌ แบบเก่า (ผิด): เรียกเฉยๆ มันจะวิ่งไปถาม DB (ซึ่ง DB ยังเขียนไม่เสร็จ)
        # recs, warns, comorbs, complis = services.process_patient_realtime(data['id']) 
        
        # ✅ แบบใหม่ (ถูก): ยัดเยียดข้อมูล (data) เข้าไปเลย ไม่ต้องรอ DB!
        recs, warns, comorbs, complis = services.process_patient_realtime(data['id'], input_data=data)
        
        return jsonify({ "status": "ok", "exercises": recs, "warnings": warns, "comorbs": comorbs, "complis": complis })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/api/patient/<id>', methods=['GET'])
def get_patient(id):
    try:
        result = services.get_patient_profile(id)
        if not result: return jsonify({"status": "error", "message": "Not found"}), 404
        return jsonify(result)
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete/<id>', methods=['DELETE'])
def delete_patient(id):
    try:
        services.delete_patient(id)
        return jsonify({"status": "ok", "message": "Deleted"})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/api/reprocess/<id>', methods=['POST'])
def reprocess_patient(id):
    try:
        # ✅ รับ 4 ค่า
        recs, warns, comorbs, complis = services.process_patient_realtime(id)
        if recs is None: return jsonify({"status": "error", "message": "Not found"}), 404
        return jsonify({ "status": "ok", "message": "Success", "exercises": recs, "warnings": warns, "comorbs": comorbs, "complis": complis })
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500
    
if __name__ == '__main__':
    print("🚀 Server started at http://localhost:5000")
    app.run(debug=True)