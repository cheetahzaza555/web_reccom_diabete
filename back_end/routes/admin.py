from flask import Blueprint, render_template, jsonify
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