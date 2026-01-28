from flask import Blueprint, render_template, jsonify
from utils.security import admin_required # เรียกยามมาใช้
from modules.database import delete_patient # สมมติว่ามีฟังก์ชันนี้

user_bp = Blueprint('user', __name__)