# modules/auth_db.py
import psycopg2
import os
from werkzeug.security import generate_password_hash

def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT")
    )
    return conn

def create_user(username, password):
    conn = get_db_connection() # 👈 เรียกใช้ฟังก์ชันเชื่อมต่อตรงนี้
    cur = conn.cursor()
    try:
        password_hash = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, password_hash, 'user')
        )
        conn.commit()
    except Exception as e:
        print("Error creating user:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def get_user(username):
    conn = get_db_connection() # 👈 เรียกใช้ฟังก์ชันเชื่อมต่อตรงนี้
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, password_hash, role FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        return user
    finally:
        cur.close()
        conn.close()