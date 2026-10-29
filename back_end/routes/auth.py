from flask import Blueprint, redirect, render_template, request, jsonify, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from modules.auth_utils import generate_token
import random
from modules.email_utils import send_otp_email
from modules.db import (
    is_username_taken,
    register_new_patient,
    get_user_for_login,
    get_user_by_id,
    update_user_profile_db,
    update_password_db,
    get_user_by_email,
    register_google_user,
    set_user_auth_provider,
)
from modules.oauth import oauth

auth = Blueprint("auth", __name__)

@auth.route("/")
def index():
    # 1. 🌟 ถ้า "ยังไม่ได้ล็อกอิน" ให้โชว์หน้า Landing Page ที่ดึงมาจาก Figma ตามปกติ
    if "user_id" not in session:
        return render_template("landing.html") 
        
    # 2. ถ้า "ล็อกอินอยู่แล้ว" ให้เช็คตำแหน่งกลุ่มผู้ใช้ (Role)
    role = session.get("role")

    if role == "admin":
        # 🛡️ วิธีป้องกันหน้าพังที่ดีที่สุด: โยนแอดมินไปที่พาร์ทแดชบอร์ดของแอดมินโดยตรง
        return redirect(url_for("admin.dashboard_page"))
    else:
        # สำหรับ User ทั่วไป ให้พาไปหน้า Dashboard ของฝั่งคนไข้ตามปกติครับ
        return redirect(url_for("user.dashboard_page"))
    
@auth.route("/login")
def login_page():
    return render_template("login.html", error=request.args.get("error"))

@auth.route("/register")
def register_page():
    return render_template("register.html")

@auth.route("/forget_password")
def forgetpassword_page():
    return render_template("forget_password.html")

# --- Google OAuth Routes ---
@auth.route("/auth/google")
@auth.route("/auth/google/login")
def google_login():
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri, prompt="select_account")


@auth.route("/auth/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        userinfo = token.get("userinfo")
        if not userinfo:
            userinfo = oauth.google.userinfo()

        email = userinfo.get("email")
        if not email:
            return render_template("login.html", error="ไม่สามารถดึงข้อมูลอีเมลจากบัญชี Google ได้")

        # 1. ตรวจสอบว่าผู้ใช้มีอยู่ในระบบแล้วหรือยัง
        user = get_user_by_email(email)

        # 2. ถ้ายังไม่มี ให้ลงทะเบียนใหม่อัตโนมัติ
        if not user:
            firstname = userinfo.get("given_name") or userinfo.get("name", "").split(" ")[0] or "GoogleUser"
            lastname = userinfo.get("family_name") or ""
            reg_result = register_google_user(email, firstname, lastname)
            if not reg_result.get("success"):
                return render_template("login.html", error=f"ไม่สามารถลงทะเบียนบัญชี Google ได้: {reg_result.get('message')}")
            user = get_user_by_email(email)
        else:
            # หากมีบัญชีอยู่แล้ว แต่ล็อกอินผ่าน Google ให้อัปเดต authProvider เป็น google
            if user.get("auth_provider") != "google":
                set_user_auth_provider(user.get("patient_id"), "google")
                user["auth_provider"] = "google"

        if not user:
            return render_template("login.html", error="เกิดข้อผิดพลาดในการโหลดข้อมูลผู้ใช้งาน")

        # 3. กำหนด Session สำหรับการเข้าสู่ระบบ
        clean_pid = str(user.get("patient_id", "")).replace("Patient", "")
        session["user_id"] = clean_pid
        session["username"] = user.get("username", "")
        session["role"] = user.get("role", "user")
        session["firstname"] = user.get("firstname", "")
        session["lastname"] = user.get("lastname", "")
        session["email"] = user.get("email", email)

        # 4. Redirect ตาม Role ของผู้ใช้
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin.dashboard_page"))
        else:
            return redirect(url_for("user.dashboard_page"))

    except Exception as e:
        print(f"Google login error: {e}")
        return render_template("login.html", error=f"เกิดข้อผิดพลาดในการเข้าสู่ระบบด้วย Google: {str(e)}")


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

        if not (8 <= len(password) <= 12):
            return jsonify({"error": "รหัสผ่านต้องมีความยาว 8–12 ตัวอักษร"}), 400

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

        if not user:
            return jsonify({"status": "error", "message": "ไม่พบผู้ใช้งาน"}), 401

        # 2. นำ Hash จาก GraphDB มาเทียบกับรหัสที่ผู้ใช้พิมพ์
        if not check_password_hash(user["password_hash"], data["password"]):
            return jsonify({"status": "error", "message": "รหัสผ่านไม่ถูกต้อง"}), 401
        
        # 3. เซ็ต Session โดยใช้คีย์ที่ดึงมาจาก GraphDB
        session["user_id"] = user.get("patient_id", "")
        session["username"] = user.get("username", "")
        session["role"] = user.get("role", "user")
        session["firstname"] = user.get("firstname", "")
        session["lastname"] = user.get("lastname", "")
        session['email'] = user.get('email', '')

        token = generate_token(user["patient_id"], user["username"], user["role"])
        return jsonify({"token": token, 
            "status": "success",
            "role": session.get("role", "user")})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth.route("/api/current_user", methods=["GET"])
def get_current_user():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        user_id = session["user_id"]
        user_data = get_user_by_id(user_id)
        
        if user_data:
            return jsonify(user_data)
        else:
            return jsonify({"error": "User not found"}), 404
            
    except Exception as e:
        print("Error fetching current user:", e)
        return jsonify({"error": str(e)}), 500
    
@auth.route("/api/check_username", methods=["POST", "GET"])
def check_username():
    try:
        if request.method == "POST":
            data = request.json or {}
            username = (data.get("username") or "").strip()
        else:
            username = (request.args.get("username") or "").strip()

        if not username:
            return jsonify({"available": False, "taken": False, "message": ""})

        taken = is_username_taken(username)
        return jsonify({
            "available": not taken,
            "taken": taken,
            "message": "ชื่อบัญชีผู้ใช้นี้มีผู้ใช้งานแล้ว" if taken else "สามารถใช้ชื่อบัญชีผู้ใช้นี้ได้"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- 1. API สำหรับส่ง OTP ไปที่อีเมล ---
@auth.route("/api/request_otp", methods=["POST"])
def request_otp():
    try:
        data = request.json or {}

        # 1. เช็คก่อนว่ามาจากหน้าไหน (ถ้าหน้าตั้งค่าจะส่ง action = 'update_settings' มา)
        action = data.get("action", "register")

        # 2. ดึงอีเมลให้ถูกที่
        if action in ("update_settings", "update_profile", "update_password", "update_admin_settings", "update_admin_profile", "update_admin_password"): 
            email = session.get('email') or data.get('email')
            if email and not session.get('email'):
                session['email'] = email
        else:
            email = data.get('email')
            username = (data.get('username') or '').strip()
            if username and is_username_taken(username):
                return jsonify({"error": "ชื่อบัญชีผู้ใช้นี้มีผู้ใช้งานแล้ว กรุณาตั้งชื่อบัญชีผู้ใช้อื่น"}), 400

        if not email:
            return jsonify({"error": "ไม่พบข้อมูลอีเมล กรุณาระบุอีเมล"}), 400

        # 3. สุ่มรหัส OTP 6 หลัก
        otp_code = str(random.randint(100000, 999999))
        
        # 4. เก็บ OTP ไว้ใน Session ชั่วคราวเพื่อรอตรวจ
        session['register_otp'] = otp_code
        session['register_email'] = email 

        # 5. ส่ง action พ่วงไปด้วย
        success = send_otp_email(email, otp_code, action)
        
        if success:
            return jsonify({"status": "ok", "message": "ส่ง OTP สำเร็จ"})
        else:
            return jsonify({"error": "ไม่สามารถส่งอีเมลได้ กรุณาลองใหม่"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth.route("/api/forgot_password_request", methods=["POST"])
def forgot_password_request():
    try:
        data = request.json
        username = data.get("username", "").strip()
        
        # 1. ค้นหาผู้ใช้จาก GraphDB ด้วย username
        user = get_user_for_login(username)
        if not user:
            return jsonify({"error": "ไม่พบชื่อผู้ใช้งานนี้ในระบบ"}), 404
            
        email = user.get("email")
        if not email:
            return jsonify({"error": "บัญชีนี้ยังไม่ได้ผูกอีเมลไว้ ไม่สามารถรีเซ็ตได้"}), 400

        # 2. สุ่มและเก็บรหัส OTP
        otp_code = str(random.randint(100000, 999999))
        session['forgot_otp'] = otp_code
        session['forgot_username'] = username
        session['forgot_patient_id'] = user.get("patient_id")

        # 3. สั่งส่งอีเมล
        success = send_otp_email(email, otp_code, action="forgot_password")
        
        if success:
            masked_email = email[:2] + "***" + email[email.find("@")-1:]
            return jsonify({"status": "ok", "masked_email": masked_email})
        else:
            return jsonify({"error": "ไม่สามารถส่งอีเมลได้"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth.route("/api/forgot_password_reset", methods=["POST"])
def forgot_password_reset():
    try:
        data = request.json
        user_otp = data.get("otp")
        new_password = data.get("new_password")
        
        saved_otp = session.get('forgot_otp')
        patient_id = session.get('forgot_patient_id')
        
        if not saved_otp or user_otp != saved_otp:
            return jsonify({"error": "รหัส OTP ไม่ถูกต้อง หรือหมดอายุ"}), 400
            
        if not patient_id:
            return jsonify({"error": "เกิดข้อผิดพลาดของระบบ (Session หมดอายุ)"}), 400

        if not new_password or not (8 <= len(new_password) <= 12):
            return jsonify({"error": "รหัสผ่านต้องมีความยาว 8–12 ตัวอักษร"}), 400

        # เข้ารหัสผ่านใหม่
        new_hash = generate_password_hash(new_password)
        
        success = update_password_db(patient_id, new_hash)
        
        if success:
            session.pop('forgot_otp', None)
            return jsonify({"status": "ok", "message": "เปลี่ยนรหัสผ่านสำเร็จ"})
        else:
            return jsonify({"error": "ไม่สามารถอัปเดตฐานข้อมูลได้"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500
