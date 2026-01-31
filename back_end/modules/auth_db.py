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

def create_user(username, password, firstname=None, lastname=None, email=None):
    conn = get_db_connection() # เชื่อมต่อฐานข้อมูล
    cur = conn.cursor()
    try:
        password_hash = generate_password_hash(password)
        
        cur.execute(
            """
            INSERT INTO users (username, password_hash, firstname, lastname, email, role) 
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (username, password_hash, firstname, lastname, email, 'user')
        )
        
        conn.commit()
        print(f"User {username} created successfully.") 
        
    except Exception as e:
        print("Error creating user:", e)
        conn.rollback()
        raise e 
        
    finally:
        cur.close()
        conn.close()

# ในไฟล์ที่เก็บฟังก์ชัน database (เช่น auth.db หรือ models.py)

def get_user(identifier):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, username, password_hash, role 
            FROM users 
            WHERE username = %s OR email = %s
            """,
            (identifier, identifier) # ส่งตัวแปรเข้าไป 2 รอบ เพื่อแทนที่ %s ทั้งสองตำแหน่ง
        )
        
        user = cur.fetchone()
        return user # จะคืนค่าเป็น tuple (id, username, hash, role) หรือ None

    except Exception as e:
        print("Error getting user:", e)
        return None
    finally:
        cur.close()
        conn.close()