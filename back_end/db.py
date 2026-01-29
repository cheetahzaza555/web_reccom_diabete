import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="user_auth_db",
        user="postgres",
        password="1234"
    )