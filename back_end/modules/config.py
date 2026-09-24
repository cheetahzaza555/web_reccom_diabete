<<<<<<< HEAD
# ตั้งค่า GraphDB
REPO_NAME = "Project" 
GRAPHDB_BASE = "http://localhost:7200/repositories"
=======
import os
from dotenv import load_dotenv

# โหลดตัวแปรจากไฟล์ .env
load_dotenv()

# ดึง URL และ ชื่อ Repo มาจาก .env (ถ้าหาไม่เจอให้ใช้ค่า Default ด้านหลัง)
GRAPHDB_URL = os.getenv("GRAPHDB_URL", "http://26.118.79.77:7200").rstrip("/")
REPO_NAME = os.getenv("GRAPHDB_REPO", "Project")

# เอามาประกอบร่างกันใน Python
GRAPHDB_BASE = f"{GRAPHDB_URL}/repositories"
>>>>>>> 17c103169a337a3766553a5a745813c721a4e545
GRAPHDB_READ = f"{GRAPHDB_BASE}/{REPO_NAME}"
GRAPHDB_WRITE = f"{GRAPHDB_BASE}/{REPO_NAME}/statements"

# ปริ้นเช็คตอนรัน
print(f"✅ GraphDB Read Endpoint: {GRAPHDB_READ}")
print(f"✅ GraphDB Write Endpoint: {GRAPHDB_WRITE}")