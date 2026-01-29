from flask import Blueprint, render_template, jsonify
from utils.security import admin_required # เรียกยามมาใช้
from modules.database import delete_patient # สมมติว่ามีฟังก์ชันนี้

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
def user_dashboard():
    return render_template('user/index.html')

@user_bp.route('/recommendations')
def user_recommendations():
    return render_template('user/rec_1.html')

@user_bp.route('/exercises')
def user_exercise():
    return render_template('user/exercise.html')

@user_bp.route('/knowledge')
def user_knowledge():
    return render_template('user/extraknowledge.html')