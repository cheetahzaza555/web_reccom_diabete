import bcrypt
import psycopg2
import os
from flask import Flask, request, jsonify, render_template , session ,redirect
from modules.database import get_patient_profile, delete_patient, save_raw_patient_data
from modules.logic import process_patient_realtime
from flask_cors import CORS
from flask import request, jsonify
from dotenv import load_dotenv

load_dotenv()

print("DB_HOST =", os.getenv("DB_HOST"))
print("DB_NAME =", os.getenv("DB_NAME"))
print("DB_USER =", os.getenv("DB_USER"))
print("DB_PASS =", os.getenv("DB_PASS"))
print("DB_PORT =", os.getenv("DB_PORT"))

app = Flask(__name__)
app.secret_key = "secret1234"
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    port=os.getenv("DB_PORT")
)

cursor = conn.cursor()
CORS(app)

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "index.html",
        username=session.get("username"),
        role=session.get("role")
    )


@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

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

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.json
        username = data.get("username")
        password = data.get("password")

        cursor.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username=%s",
            (username,)
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({"message": "User not found"}), 401

        # 🔐 เช็ค password ด้วย bcrypt
        if not bcrypt.checkpw(
            password.encode("utf-8"),
            user[2].encode("utf-8")
        ):
            return jsonify({"message": "Wrong password"}), 401

        # ✅ เก็บ session
        session["user_id"] = user[0]
        session["username"] = user[1]
        session["role"] = user[3]

        return jsonify({"message": "Login success"})

    except Exception as e:
        print("LOGIN ERROR:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.json
        username = data["username"]
        password = data["password"]

        hashed = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, hashed, "user")
        )
        conn.commit()

        return jsonify({"message": "Register success"})

    except Exception as e:
        print("REGISTER ERROR:", e)
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True, port=5000)