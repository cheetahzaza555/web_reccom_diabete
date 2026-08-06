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

def insert_exercise_to_ontology_v2(existing_id=None, name=None, exercise_type=None, mets=None, youtube_id=None):
    try:
        from SPARQLWrapper import SPARQLWrapper
        from modules.config import GRAPHDB_WRITE 
        import random
        
        sparql_write_client = SPARQLWrapper(GRAPHDB_WRITE)
        base_prefix = "http://example.org/diabetes#"
        
        final_id = existing_id if existing_id else f"17{random.randint(100, 999)}"
        subject_uri = f"<{base_prefix}{final_id}>"
        
        # ปรับแก้ให้ใช้ exercise_type ตรงๆ โดยไม่ส่ง string ซ้ำซ้อน
        type_uri = f"<{base_prefix}{exercise_type}>"
        
        parent_class = None
        middle_class = None

        # 🌳 1. จำแนกกลุ่มตามผัง Ontology
        # [กลุ่ม Aerobic - WeightBearing]
        if exercise_type in ["Walking", "Running", "Dancing", "WeightBearingAerobicSport"]:
            parent_class = "ex:Aerobic"
            middle_class = "ex:WeightBearingAerobicExercise"

        # [กลุ่ม Aerobic - NonWeightBearing]
        elif exercise_type in ["Bicycling", "WaterActivity", "NonWeightBearingAerobicSport"]:
            parent_class = "ex:Aerobic"
            middle_class = "ex:NonWeightBearingAerobicExercise"

        # [กลุ่ม Resistance]
        elif exercise_type in ["WeightBearingResistanceExercise"]:
            parent_class = "ex:Resistance"
            middle_class = "ex:WeightBearingResistanceExercise"

        elif exercise_type in ["NonWeightBearingResistanceExercise"]:
            parent_class = "ex:Resistance"
            middle_class = "ex:NonWeightBearingResistanceExercise"

        # [กลุ่ม Stretching - เพิ่มคำว่า StretchingExercise และ ResistanceAndStretchingExercise]
        elif exercise_type in ["Stretching", "StretchingExercise", "ResistanceAndStretchingExercise"]: 
            parent_class = "ex:StretchingExercise"
            middle_class = None
            
        else:
            # 🚨 แก้ไข Fallback: ถ้าไม่รู้จัก ให้ใช้ประเภทที่ส่งมาเป็น parent แทน ห้ามใช้ ex:Aerobic มั่ว
            parent_class = f"ex:{exercise_type}"

        # 🌳 2. สร้าง Triple
        middle_class_triple = f"{subject_uri} rdf:type {middle_class} ." if middle_class else ""

        insert_query = f"""
        PREFIX ex: <{base_prefix}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        INSERT DATA {{
            {subject_uri} rdf:type owl:NamedIndividual .
            {subject_uri} rdf:type ex:Exercise .
            {subject_uri} rdf:type {parent_class} .
            
            {middle_class_triple}
            
            {subject_uri} ex:hasKindOfExercise {type_uri} .
            {subject_uri} rdfs:label "{name}" .
            {subject_uri} ex:metValue "{float(mets)}"^^xsd:decimal .
            {subject_uri} ex:hasYoutubeID "{youtube_id if youtube_id else ''}" .
        }}
        """

        sparql_write_client.setQuery(insert_query)
        sparql_write_client.setMethod('POST')
        sparql_write_client.query()

        print(f"💾 [GraphDB] ซิงค์ข้อมูล ID #{final_id} เสร็จสิ้น (Parent: {parent_class})")
        return {"success": True, "message": "ซิงค์สำเร็จ"}
        
    except Exception as e:
        print(f"❌ Error sync ontology: {e}")
        return {"success": False, "message": str(e)}

# 💡 และอย่าลืมเปลี่ยนไส้ในของฟังก์ชันเพิ่มอันเก่า (insert_exercise_to_ontology) ให้เรียกใช้งานผ่านตัว v2 นี้ด้วยนะ ตัวอย่างเช่น:
def insert_exercise_to_ontology(name, exercise_type, mets, youtube_id=None):
    return insert_exercise_to_ontology_v2(None, name, exercise_type, mets, youtube_id)
    
def delete_exercise_from_ontology(exercise_id):
    """ฟังก์ชันสำหรับลบความสัมพันธ์ทั้งหมดของท่าออกกำลังกายตาม ID ออกจาก GraphDB"""
    try:
        from SPARQLWrapper import SPARQLWrapper
        from modules.config import GRAPHDB_WRITE
        
        sparql_write_client = SPARQLWrapper(GRAPHDB_WRITE)
        base_prefix = "http://example.org/diabetes#"
        subject_uri = f"<{base_prefix}{exercise_id}>"
        
        # คำสั่งล้างไตรภาค (Triples) ทุกรูปแบบที่เกี่ยวข้องกับ ID ตัวนี้
        delete_query = f"""
        PREFIX ex: <{base_prefix}>
        
        DELETE WHERE {{
            {subject_uri} ?p ?o .
        }}
        """
        
        sparql_write_client.setQuery(delete_query)
        sparql_write_client.setMethod('POST')
        sparql_write_client.query()
        
        print(f"🗑️ [GraphDB Success] ลบข้อมูลไอดี #{exercise_id} ออกจากระบบเรียบร้อย")
        return {"success": True, "message": "ลบข้อมูลสำเร็จ"}
    except Exception as e:
        print(f"❌ Error deleting exercise: {e}")
        return {"success": False, "message": str(e)}