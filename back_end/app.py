from flask import Flask
import psycopg2
import os
from routes.user import user_bp
from flask_cors import CORS
from dotenv import load_dotenv
from routes.auth import auth

load_dotenv()

print("DB_HOST =", os.getenv("DB_HOST"))
print("DB_NAME =", os.getenv("DB_NAME"))
print("DB_USER =", os.getenv("DB_USER"))
print("DB_PASS =", os.getenv("DB_PASS"))
print("DB_PORT =", os.getenv("DB_PORT"))

app = Flask(__name__)
app.secret_key = "secret1234"
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    port=os.getenv("DB_PORT")
)

cursor = conn.cursor()
CORS(app)

app.register_blueprint(auth)

app.register_blueprint(user_bp, url_prefix='/user')

if __name__ == '__main__':
    app.run(debug=True, port=5000)