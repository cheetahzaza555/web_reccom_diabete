# modules/db/admin_repository.py
"""
ฟังก์ชันสำหรับฝั่ง Admin: สถิติ dashboard, จัดการผู้ใช้/สิทธิ์, ข้อมูลสุขภาพผู้ป่วย

หมายเหตุ (แก้บั๊ก): ไฟล์ modules/admin.py เดิมมีฟังก์ชันชื่อ
`get_all_patients_management()` ถูกนิยามซ้ำ 2 ครั้ง (ตัวหลังทับตัวแรก)
จึงแยกให้เป็นคนละชื่อดังนี้:
  - get_patient_health_summary()  -> ดึงข้อมูลสุขภาพ (bmi, fpg, type) สำหรับหน้าดูสุขภาพผู้ใช้
  - get_all_users_with_roles()    -> ดึงข้อมูล role สำหรับหน้า /users (จัดการสิทธิ์)
"""

from SPARQLWrapper import POST, SPARQLWrapper, JSON
from modules.config import GRAPHDB_READ, GRAPHDB_WRITE


def get_admin_dashboard_stats():
    """ฟังก์ชันดึงตัวเลขสถิติแยกคิวรี เพื่อความแม่นยำ 100% ไม่เกิดการคูณซ้ำ"""
    sparql = SPARQLWrapper(GRAPHDB_READ)
    stats = {"total_patients": 0, "total_exercises": 0, "total_mets": 0}

    # 1. นับจำนวนคนไข้จริง (นับเฉพาะตัวที่มีคลาส Patient)
    query_patients = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT (COUNT(DISTINCT ?patient) AS ?count) WHERE {
        ?patient a ex:Patient .
    }
    """

    # 2. นับจำนวนท่าออกกำลังกายที่ไม่ซ้ำกันเลยในระบบ (DISTINCT ?exercise)
    query_exercises = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT (COUNT(DISTINCT ?exercise) AS ?count) WHERE {
        ?p ex:recommendedExercise ?exercise .
    }
    """

    # 3. นับจำนวน "รายการบันทึกการแนะนำการออกกำลังกาย" ทั้งหมดที่เกิดขึ้นในระบบจริง
    query_recommendations = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT (COUNT(?exercise) AS ?count) WHERE {
        ?p ex:recommendedExercise ?exercise .
    }
    """

    try:
        sparql.setReturnFormat(JSON)

        sparql.setQuery(query_patients)
        res_p = sparql.query().convert()
        stats["total_patients"] = int(res_p["results"]["bindings"][0]["count"]["value"])

        sparql.setQuery(query_exercises)
        res_e = sparql.query().convert()
        stats["total_exercises"] = int(res_e["results"]["bindings"][0]["count"]["value"])

        sparql.setQuery(query_recommendations)
        res_r = sparql.query().convert()
        stats["total_mets"] = int(res_r["results"]["bindings"][0]["count"]["value"])

    except Exception as e:
        print("❌ [Admin Module Error] เกิดข้อผิดพลาดขณะ Query สถิติรวม:", e)

    return stats


def get_recent_registered_users():
    """ดึงรายชื่อผู้ป่วยที่ลงทะเบียนในระบบมาแสดงในตารางกิจกรรมล่าสุด"""
    sparql = SPARQLWrapper(GRAPHDB_READ)
    user_list = []

    query = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT DISTINCT ?username ?fname ?lname WHERE {
        ?p a ex:Patient .
        OPTIONAL { ?p ex:username ?username . }
        OPTIONAL { ?p ex:firstname ?fname . }
        OPTIONAL { ?p ex:lastname ?lname . }
    } LIMIT 5
    """
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()

        for row in results["results"]["bindings"]:
            u_name = row.get("username", {}).get("value", "Unknown")
            f_name = row.get("fname", {}).get("value", u_name)
            l_name = row.get("lname", {}).get("value", "")

            user_list.append({
                "firstname": f_name,
                "lastname": l_name
            })
    except Exception as e:
        print("❌ [Admin Module Error] เกิดข้อผิดพลาดขณะ Query รายชื่อผู้ใช้ล่าสุด:", e)

    return user_list


def get_patient_health_summary():
    """
    ดึงรายชื่อผู้ป่วยทุกคนพร้อมข้อมูลสุขภาพสำคัญ (ประเภทเบาหวาน, FPG, BMI)
    ใช้สำหรับหน้าที่ Admin กดเข้าไปดูข้อมูลสุขภาพของผู้ใช้แต่ละคน
    """
    sparql = SPARQLWrapper(GRAPHDB_READ)
    patient_list = []

    query = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT DISTINCT ?p ?username ?fname ?lname ?type ?fpg ?bmi WHERE {
        ?p a ex:Patient .
        OPTIONAL { ?p ex:username ?username . }
        OPTIONAL { ?p ex:firstname ?fname . }
        OPTIONAL { ?p ex:lastname ?lname . }
        OPTIONAL { ?p ex:diabetType ?typeUri . BIND(STRAFTER(STR(?typeUri), "#") AS ?type) }
        
        OPTIONAL { ?p ex:hasPhysicalExam ?pe . OPTIONAL { ?pe ex:hasBMI ?bmi } }
        OPTIONAL { ?p ex:hasLabExam ?le . OPTIONAL { ?le ex:hasFPG ?fpg } }
    }
    """
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()

        for row in results["results"]["bindings"]:
            p_uri = row["p"]["value"]
            p_id = p_uri.split("#")[-1].replace("Patient", "") if "#" in p_uri else p_uri

            patient_list.append({
                "id": p_id,
                "username": row.get("username", {}).get("value", "-"),
                "firstname": row.get("fname", {}).get("value", "-"),
                "lastname": row.get("lname", {}).get("value", "-"),
                "type": row.get("type", {}).get("value", "ไม่ระบุ"),
                "bmi": row.get("bmi", {}).get("value", "-"),
                "fpg": row.get("fpg", {}).get("value", "-")
            })
    except Exception as e:
        print("❌ [Admin Module Error] ไม่สามารถดึงรายชื่อผู้ใช้ทั้งหมดได้:", e)

    return patient_list


def get_all_users_with_roles():
    """ดึงรายชื่อผู้ใช้ทุกคนพร้อมตำแหน่งสิทธิ์ (Role) ปัจจุบันในระบบ (ใช้ในหน้า /users)"""
    sparql = SPARQLWrapper(GRAPHDB_READ)
    user_list = []

    query = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT DISTINCT ?p ?username ?fname ?lname ?role WHERE {
        ?p a ex:Patient .
        OPTIONAL { ?p ex:username ?username . }
        OPTIONAL { ?p ex:firstname ?fname . }
        OPTIONAL { ?p ex:lastname ?lname . }
        OPTIONAL { ?p ex:role ?role . } 
    }
    """
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()

        for row in results["results"]["bindings"]:
            p_uri = row["p"]["value"]
            p_id = p_uri.split("#")[-1].replace("Patient", "") if "#" in p_uri else p_uri

            user_list.append({
                "id": p_id,
                "username": row.get("username", {}).get("value", "-"),
                "firstname": row.get("fname", {}).get("value", "-"),
                "lastname": row.get("lname", {}).get("value", "-"),
                "role": row.get("role", {}).get("value", "user")
            })
    except Exception as e:
        print("❌ [Admin Error] ดึงรายชื่อผู้ใช้ล้มเหลว:", e)

    return user_list


def update_user_role_in_graphdb(user_id, new_role):
    """
    ฟังก์ชันส่งคำสั่ง SPARQL UPDATE ไปแก้ไขสิทธิ์ (ex:role) ในคลังข้อมูล GraphDB
    """
    update_query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    
    DELETE {{
        ex:Patient{user_id} ex:role ?old_role .
    }}
    INSERT {{
        ex:Patient{user_id} ex:role "{new_role}" .
    }}
    WHERE {{
        ex:Patient{user_id} a ex:Patient .
        OPTIONAL {{ ex:Patient{user_id} ex:role ?old_role . }}
    }}
    """

    try:
        sparql = SPARQLWrapper(GRAPHDB_WRITE)
        sparql.setMethod(POST)
        sparql.setQuery(update_query)
        sparql.query()

        print(f"✅ [GraphDB Sync] อัปเดตสิทธิ์ Patient{user_id} เป็น '{new_role}' ในเซิร์ฟเวอร์หลักแล้ว")
        return True, "อัปเดตสิทธิ์ในฐานข้อมูลสำเร็จ"

    except Exception as e:
        error_msg = str(e)
        print(f"❌ [GraphDB Error] ไม่สามารถบันทึกค่าลงคลังข้อมูลได้: {error_msg}")
        return False, error_msg