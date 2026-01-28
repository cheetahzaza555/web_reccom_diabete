# routes/auth.py
from flask import Blueprint, redirect, render_template, request, jsonify, session
from werkzeug.security import check_password_hash
from modules.auth_db import create_user, get_user
from modules.auth_utils import generate_token 

auth = Blueprint("auth", __name__)

@auth.route("/")
def index():
    # 1. เช็คก่อนว่าล็อกอินหรือยัง
    if "user_id" not in session:
        return redirect("/login")

    # 2. ดึง Role ออกมาดูว่าเป็นใคร
    role = session.get("role")

    # 3. พาไปเปิดห้องให้ถูกคน
    if role == "admin":
        # ถ้าเป็น admin ให้ไปเปิดไฟล์ในโฟลเดอร์ admin
        return render_template(
            "admin/index.html", 
            username=session.get("username"),
            role=role
        )
    else:
        # ถ้าเป็น user ธรรมดา ให้ไปเปิดไฟล์ในโฟลเดอร์ user
        return render_template(
            "user/index.html",   # 👈 ต้องระบุชื่อโฟลเดอร์นำหน้าแบบนี้ครับ
            username=session.get("username"),
            role=role
        )
    
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
    data = request.json
    create_user(data["username"], data["password"])
    return jsonify({"status": "ok"})

@auth.route("/api/login", methods=["POST"])
def login():
    data = request.json
    user = get_user(data["username"])

    if not user:
        return jsonify({"status": "error"}), 401

    uid, uname, pw_hash, role = user
    if not check_password_hash(pw_hash, data["password"]):
        return jsonify({"status": "error"}), 401
    
    session["user_id"] = uid
    session["username"] = uname
    session["role"] = role

    token = generate_token(uid, uname, role)
    return jsonify({"token": token})
