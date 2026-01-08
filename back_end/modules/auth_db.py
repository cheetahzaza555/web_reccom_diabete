import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

conn = psycopg2.connect(
    dbname="user_auth_db",
    user="postgres",
    password="1234",
    host="localhost",
    port="5432"
)     

def create_user(username, password, role="USER"):
    cur = conn.cursor()
    pw_hash = generate_password_hash(password)
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
        (username, pw_hash, role)
    )
    conn.commit()
    cur.close()

def get_user(username):
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username=%s",
        (username,)
    )
    row = cur.fetchone()
    cur.close()
    return row
