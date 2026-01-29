import bcrypt
import jwt
from datetime import datetime, timedelta
from db import get_db_connection

SECRET_KEY = "super_secret_key"

# ======================
# Register
# ======================
def register_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    try:
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, hashed.decode())
        )
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()

# ======================
# Login
# ======================
def login_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = %s",
        (username,)
    )
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        return None

    user_id, username, password_hash, role = user

    if bcrypt.checkpw(password.encode(), password_hash.encode()):
        return generate_token(user_id, username, role)

    return None

# ======================
# JWT
# ======================
def generate_token(user_id, username, role):
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=2)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except:
        return None