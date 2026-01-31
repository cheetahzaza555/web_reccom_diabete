# routes/auth.py
from flask import Blueprint, redirect, render_template, request, jsonify, session
from werkzeug.security import check_password_hash
from modules.auth_db import create_user, get_user
from modules.auth_utils import generate_token
from modules.auth_db import get_db_connection

auth = Blueprint("auth", __name__)

@auth.route("/")
def index():
    if "user_id" not in session:
        return redirect("/login")

    role = session.get("role")

    if role == "admin":
        return render_template(
            "admin/index.html", 
            username=session.get("username"),
            role=role
        )
    else:
        return render_template(
            "user/index.html",   
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
    try:
        data = request.json
        firstname = data.get("firstname")
        lastname = data.get("lastname")
        email = data.get("email")
        username = data["username"]
        password = data["password"]
        create_user(username, password, firstname, lastname, email)
        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth.route("/api/login", methods=["POST"])
def login():
    data = request.json
    
    user = get_user(data["username"]) 

    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 401

    uid, uname, pw_hash, role = user 

    if not check_password_hash(pw_hash, data["password"]):
        return jsonify({"status": "error", "message": "Wrong password"}), 401
    
    session["user_id"] = uid
    session["username"] = uname
    session["role"] = role

    token = generate_token(uid, uname, role)
    return jsonify({"token": token})

# เพิ่ม Route นี้เพื่อให้หน้าเว็บดึงข้อมูลชื่อ/นามสกุลไปแสดงได้
@auth.route("/api/current_user", methods=["GET"])
def get_current_user():
    # 1. เช็คก่อนว่า Login หรือยัง (เช็คจาก Session)
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session["user_id"]
    
    # 2. เชื่อมต่อ Database เพื่อดึงชื่อจริง/นามสกุล
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # ดึงข้อมูล: firstname, lastname, username, role
        cur.execute(
            "SELECT firstname, lastname, username, role FROM users WHERE id = %s", 
            (user_id,)
        )
        user = cur.fetchone()
        
        if user:
            # 3. แปลงข้อมูลจาก Tuple เป็น Dictionary (JSON)
            # ต้องเรียงลำดับให้ตรงกับ SELECT นะครับ
            # user[0]=firstname, user[1]=lastname, user[2]=username, user[3]=role
            user_data = {
                "id": user_id,
                "firstname": user[0],
                "lastname": user[1],
                "username": user[2],
                "role": user[3]
            }
            return jsonify(user_data)
        else:
            return jsonify({"error": "User not found"}), 404
            
    except Exception as e:
        print("Error fetching current user:", e)
        return jsonify({"error": str(e)}), 500
        
    finally:
        cur.close()
        conn.close()