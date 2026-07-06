from functools import wraps
from flask import session, flash, redirect, url_for, jsonify, request


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('กรุณาล็อกอินก่อน', 'error')
            return redirect(url_for('auth.login'))

        if session.get('role') != 'admin':
            flash('เข้าไม่ได้! สำหรับผู้ดูแลระบบเท่านั้น', 'error')
            return redirect(url_for('user.index'))  # ดีดกลับหน้าแรก

        return f(*args, **kwargs)
    return decorated_function


def login_required(f):
# เช็คแค่ว่าล็อกอินแล้วหรือยัง 
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # ถ้าเป็นการเรียกแบบ AJAX/API (Content-Type เป็น JSON) ให้ตอบ JSON แทนการ redirect
            if request.is_json or request.path.startswith('/user/api/'):
                return jsonify({"status": "error", "message": "กรุณาล็อกอินก่อน"}), 401

            flash('กรุณาล็อกอินก่อน', 'error')
            return redirect(url_for('auth.login_page'))

        return f(*args, **kwargs)
    return decorated_function