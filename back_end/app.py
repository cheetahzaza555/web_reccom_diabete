from flask import Flask, render_template, jsonify, request
import services
import auth
from auth import verify_token

app = Flask(__name__)

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    token = request.headers.get("Authorization")
    user_id = verify_token(token)

    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.json
    recs, warns, comorbs, complis = services.process_patient_realtime(
        str(user_id), input_data=data
    )

    return jsonify({
        "status": "ok",
        "exercises": recs,
        "warnings": warns
    })
    
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


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if auth.register_user(data['username'], data['password']):
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "User exists"}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    token = auth.login_user(data['username'], data['password'])
    if token:
        return jsonify({"status": "ok", "token": token})
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')
    
if __name__ == '__main__':
    print("🚀 Server started at http://localhost:5000")
    app.run(debug=True)