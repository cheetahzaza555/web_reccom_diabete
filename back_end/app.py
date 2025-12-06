from flask import Flask, render_template, jsonify, request
import services

app = Flask(__name__)

# --- หน้าแรก ---
@app.route('/')
def home():
    return render_template('index.html')

# --- API 1: เพิ่มข้อมูล + ประมวลผล ---
@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.json
    try:
        # 1. บันทึกข้อมูลดิบลง DB ก่อน
        services.save_raw_patient_data(data)
        
        # 2. สั่งรัน Reasoner
        recs, warns = services.process_patient_realtime(data['id'])
        
        return jsonify({
            "status": "ok",
            "exercises": recs,
            "warnings": warns
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API 2: ค้นหาข้อมูลผู้ป่วย ---
@app.route('/api/patient/<id>', methods=['GET'])
def get_patient(id):
    try:
        print(f"Fetching patient profile for ID: {id}")
        result = services.get_patient_profile(id)
        if not result:
            return jsonify({"status": "error", "message": "Not found"}), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- API 3: ลบข้อมูล ---
@app.route('/api/delete/<id>', methods=['DELETE'])
def delete_patient(id):
    try:
        services.delete_patient(id)
        return jsonify({"status": "ok", "message": f"ลบข้อมูล ID {id} สำเร็จ"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
# --- API 4: รันกฎใหม่ (Reprocess) ---
@app.route('/api/reprocess/<id>', methods=['POST'])
def reprocess_patient(id):
    try:
        recs, warns = services.process_patient_realtime(id)
        
        if recs is None:
            return jsonify({"status": "error", "message": "ไม่พบข้อมูลผู้ป่วยใน DB"}), 404
            
        return jsonify({
            "status": "ok", 
            "message": "รันกฎใหม่สำเร็จ",
            "exercises": recs,
            "warnings": warns
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
if __name__ == '__main__':
    print("🚀 Server started at http://localhost:5000")
    app.run(debug=True)