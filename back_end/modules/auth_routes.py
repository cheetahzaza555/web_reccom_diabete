from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from modules.auth_db import create_user, get_user
from modules.auth_utils import generate_token

auth = Blueprint("auth", __name__)

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

    token = generate_token(uid, uname, role)
    return jsonify({"token": token})
