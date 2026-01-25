from functools import wraps
from flask import session, flash, redirect, url_for

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('กรุณาล็อกอินก่อน', 'error')
            return redirect(url_for('auth.login'))
        
        if session.get('role') != 'admin':
            flash('เข้าไม่ได้! สำหรับผู้ดูแลระบบเท่านั้น', 'error')
            return redirect(url_for('user.index')) # ดีดกลับหน้าแรก
            
        return f(*args, **kwargs)
    return decorated_function