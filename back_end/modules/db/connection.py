# modules/db/connection.py
"""
การตั้งค่าเชื่อมต่อ GraphDB (SPARQL) และฟังก์ชันช่วยเหลือ (helpers)
ที่ใช้ร่วมกันในทุกไฟล์ของ modules/db/
"""

import re
from SPARQLWrapper import SPARQLWrapper, JSON, POST
from modules.config import GRAPHDB_READ, GRAPHDB_WRITE

# --- Setup Connection ---
sparql_read = SPARQLWrapper(GRAPHDB_READ)
sparql_read.setReturnFormat(JSON)

sparql_write = SPARQLWrapper(GRAPHDB_WRITE)
sparql_write.setMethod(POST)


# --- Helpers ---

def validate_id(val):
    """ตรวจสอบว่า ID ปลอดภัย (กัน SPARQL Injection เบื้องต้น)"""
    if not val:
        return False
    return bool(re.match(r'^[A-Za-z0-9_-]{1,64}$', str(val)))


def escape_sparql(text):
    """Escape อักขระพิเศษก่อนใส่ลงใน SPARQL query string"""
    if not text:
        return ""
    return str(text).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def safe_float(value):
    """แปลงค่าเป็น float อย่างปลอดภัย คืนค่า None ถ้าแปลงไม่ได้"""
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def get_thai_text(entity):
    """
    แปลงชื่อ entity เป็นข้อความภาษาไทย
    1. เช็ค description/label จาก GraphDB ก่อน
    2. ถ้าไม่มี ให้ดักแปลจาก dictionary ที่กำหนดไว้
    """
    if hasattr(entity, "description") and entity.description:
        return str(entity.description[0])
    if hasattr(entity, "label") and entity.label:
        return str(entity.label[0])

    name_str = entity.name

    # พจนานุกรมแปลภาษา (เพิ่มคำอื่นๆ ที่ต้องการแปลได้ที่นี่เลย)
    translations = {
        "NoComorbidity": "ไม่มีโรคร่วม",
        "NoGeneralComplication": "ไม่มีภาวะแทรกซ้อนทั่วไป",
        "NoOtherComplication": "ไม่มีภาวะแทรกซ้อนอื่นๆ",
        "Retinopathy": "จอประสาทตาเสื่อม (Retinopathy)",
        "HeartDisease": "โรคหัวใจ (Heart Disease)",
        "PeripheralNeuropathy": "ปลายประสาทเสื่อม (Neuropathy)",
        "AutonomicNeuropathy": "ระบบประสาทอัตโนมัติผิดปกติ"
    }

    if name_str in translations:
        return translations[name_str]

    return name_str


def safe_get_name(uri):
    """ตัดเอาเฉพาะชื่อท้าย URI (หลัง # หรือ /)"""
    if not uri:
        return ""
    return re.split(r'[#/]', uri)[-1]