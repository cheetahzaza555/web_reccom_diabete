from flask import Blueprint, redirect, render_template, request, jsonify, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash # เพิ่ม generate_password_hash
from modules.auth_utils import generate_token
import random
from modules.email_utils import send_otp_email

# เปลี่ยนมานำเข้าฟังก์ชันจาก database.py แทน (เพราะเราจะย้ายคำสั่ง SPARQL ไปรวมไว้ที่นั่น)
from modules.database import register_new_patient, get_user_for_login, get_user_by_id

auth = Blueprint("auth", __name__)

@auth.route("/")
def index():
    # 1. 🌟 ถ้า "ยังไม่ได้ล็อกอิน" ให้โชว์หน้า Landing Page ที่ดึงมาจาก Figma
    if "user_id" not in session:
        return render_template("landing.html") 
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

# --- 2. แก้ไข API Register ตัวเดิม ให้ดักตรวจ OTP ด้วย ---
@auth.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.json
        # ดึง otp ที่ผู้ใช้กรอกส่งมาด้วย
        user_otp = data.get("otp")
        email = data.get("email", "")

        # 🚨 เช็คว่า OTP ตรงกับที่สุ่มไว้ใน Session ไหม
        saved_otp = session.get('register_otp')
        saved_email = session.get('register_email')

        if not saved_otp or user_otp != saved_otp:
            return jsonify({"error": "รหัส OTP ไม่ถูกต้อง"}), 400
            
        if email != saved_email:
            return jsonify({"error": "อีเมลไม่ตรงกับที่ขอ OTP"}), 400

        # --- ถ้า OTP ผ่าน ถึงจะเอาข้อมูลไปบันทึก (โค้ดเดิมของคุณ) ---
        firstname = data.get("firstname", "")
        lastname = data.get("lastname", "")
        username = data["username"]
        password = data["password"]

        hashed_password = generate_password_hash(password)
        result = register_new_patient(username, hashed_password, firstname, lastname, email)
        
        if result["success"]:
            # เคลียร์ OTP ทิ้งเมื่อสมัครเสร็จ
            session.pop('register_otp', None)
            session.pop('register_email', None)
            return jsonify({"status": "ok", "patient_id": result["patient_id"]})
        else:
            return jsonify({"error": result["message"]}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.json
        
        # 1. ไปค้นหา User จาก GraphDB
        user = get_user_for_login(data["username"])
        print(f"DEBUG: ข้อมูล user ที่ได้จาก DB: {user}")

        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 401

        # 2. นำ Hash จาก GraphDB มาเทียบกับรหัสที่ผู้ใช้พิมพ์
        if not check_password_hash(user["password_hash"], data["password"]):
            return jsonify({"status": "error", "message": "รหัสผ่านไม่ถูกต้อง"}), 401
        
        print(f"DEBUG: ข้อมูลที่ดึงมาจากฐานข้อมูล: {user}")
        # 3. เซ็ต Session โดยใช้คีย์ที่ดึงมาจาก GraphDB
        session["user_id"] = user.get("patient_id", "")
        session["username"] = user.get("username", "")
        session["role"] = user.get("role", "user")
        session["firstname"] = user.get("firstname", "")
        session["lastname"] = user.get("lastname", "")
        session['email'] = user.get('email', '')

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
    
    # --- 1. API สำหรับส่ง OTP ไปที่อีเมล ---
@auth.route("/api/request_otp", methods=["POST"])
def request_otp():
    try:
        data = request.json
        email = data.get("email")
        if not email:
            return jsonify({"error": "กรุณาระบุอีเมล"}), 400

        # สุ่มรหัส OTP 6 หลัก
        otp_code = str(random.randint(100000, 999999))
        
        # เก็บ OTP ไว้ใน Session ชั่วคราวเพื่อรอตรวจ
        session['register_otp'] = otp_code
        session['register_email'] = email 

        # ส่งอีเมล
        success = send_otp_email(email, otp_code)
        
        if success:
            return jsonify({"status": "ok", "message": "ส่ง OTP สำเร็จ"})
        else:
            return jsonify({"error": "ไม่สามารถส่งอีเมลได้ กรุณาลองใหม่"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


