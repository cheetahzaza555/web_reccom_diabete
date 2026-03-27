from flask import Blueprint, redirect, render_template, request, jsonify, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash # เพิ่ม generate_password_hash
from modules.auth_utils import generate_token

# เปลี่ยนมานำเข้าฟังก์ชันจาก database.py แทน (เพราะเราจะย้ายคำสั่ง SPARQL ไปรวมไว้ที่นั่น)
from modules.database import register_new_patient, get_user_for_login, get_user_by_id

auth = Blueprint("auth", __name__)

@auth.route("/")
def index():
    # 1. 🌟 ถ้า "ยังไม่ได้ล็อกอิน" ให้โชว์หน้า Landing Page ที่ดึงมาจาก Figma
    if "user_id" not in session:
        return render_template("landing.html") # <--- ชี้ไปที่ไฟล์ใหม่ของเรา

    # 2. ถ้า "ล็อกอินอยู่แล้ว" ให้เช็คว่าเป็น Admin หรือ User
    role = session.get("role")

    if role == "admin":
        return render_template(
            "admin/index.html", 
            username=session.get("username"),
            role=role
        )
    else:
        # สำหรับ User ทั่วไป ให้พาไปหน้า Dashboard (ซึ่งมันจะไปเรียกใช้ templates/user/index.html ให้เองอัตโนมัติครับ)
        return redirect(url_for("user.dashboard_page"))
    
@auth.route("/login")
def login_page():
    return render_template("login.html")

@auth.route("/register")
def register_page():
    return render_template("register.html")

@auth.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

@auth.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.json
        firstname = data.get("firstname", "")
        lastname = data.get("lastname", "")
        email = data.get("email", "")
        username = data["username"]
        password = data["password"]

        # 1. เข้ารหัสผ่านก่อน (Hash) เพื่อความปลอดภัย
        hashed_password = generate_password_hash(password)

        # 2. ส่งข้อมูลทั้งหมดไปให้ GraphDB บันทึก
        result = register_new_patient(username, hashed_password, firstname, lastname, email)
        
        if result["success"]:
            return jsonify({"status": "ok", "patient_id": result["patient_id"]})
        else:
            # ถ้า username ซ้ำ หรือระบบพัง จะเด้ง error
            return jsonify({"error": result["message"]}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.json
        
        # 1. ไปค้นหา User จาก GraphDB
        user = get_user_for_login(data["username"]) 

        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 401

        # 2. นำ Hash จาก GraphDB มาเทียบกับรหัสที่ผู้ใช้พิมพ์
        if not check_password_hash(user["password_hash"], data["password"]):
            return jsonify({"status": "error", "message": "Wrong password"}), 401
        
        # 3. เซ็ต Session โดยใช้คีย์ที่ดึงมาจาก GraphDB
        session["user_id"] = user["patient_id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["firstname"] = user["firstname"]  
        session["lastname"] = user["lastname"]   

        token = generate_token(user["patient_id"], user["username"], user["role"])
        return jsonify({"token": token})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth.route("/api/current_user", methods=["GET"])
def get_current_user():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session["user_id"]
    
    try:
        # ❌ ลบโค้ด SQL Connection ออกให้หมด
        # ✅ เรียกใช้ฟังก์ชัน SPARQL เพื่อดึง Profile แทน
        user_id = session["user_id"]
        user_data = get_user_by_id(user_id) # ฟังก์ชันที่เราเพิ่งแก้ด้านบน
        
        if user_data:
            return jsonify(user_data)
        else:
            return jsonify({"error": "User not found"}), 404
            
    except Exception as e:
        print("Error fetching current user:", e)
        return jsonify({"error": str(e)}), 500