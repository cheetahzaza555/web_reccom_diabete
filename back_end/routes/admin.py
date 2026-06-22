from flask import Blueprint, render_template, jsonify ,session
from utils.security import admin_required # เรียกยามมาใช้
from modules.database import delete_patient, get_patient_profile # สมมติว่ามีฟังก์ชันนี้


admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/patient/<id>', methods=['GET'])
def get_patient(id):
    profile = get_patient_profile(id)
    if profile: 
        return jsonify({"status": "ok", **profile})
    return jsonify({"status": "error"})


@admin_bp.route('/api/patient/<id>', methods=['DELETE'])
def delete_patient_route(id):
    result = delete_patient(id)
    if result:
        return jsonify({"status": "deleted"})
    return jsonify({"status": "error"})

# 🚨 เช็คบรรทัดนี้ให้ชัวร์ว่าพิมพ์ /dashboard
@admin_bp.route("/dashboard")
def dashboard():
    # ตรวจสอบสิทธิ์นิดนึง เพื่อความปลอดภัย
    if session.get("role") != "admin":
        return redirect("/login") # ถ้าไม่ใช่แอดมินแอบเข้า ให้เด้งกลับไปหน้า login
        
    # ถ้าใช่แอดมิน ให้เรนเดอร์หน้าเว็บของแอดมิน
    return render_template("admin/index.html")