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
import random



def get_all_categories_for_dropdown():
    sparql_read = SPARQLWrapper(GRAPHDB_READ)
    """ดึงเฉพาะ Class ย่อยล่างสุด (Leaf Classes) ภายใต้ ex:Exercise"""
    query = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT DISTINCT ?cat ?label WHERE {
        # 1. ดึงเฉพาะ class ที่เป็น subClassOf ของ ex:Exercise
        ?cat rdfs:subClassOf+ ex:Exercise .
        
        # 🟢 2. กรองคลาสแม่ออก: เอาเฉพาะคลาสที่ "ไม่มีคลาสอื่นมา subClassOf ตัวมันอีก" (Leaf Class)
        FILTER NOT EXISTS {
            ?subClass rdfs:subClassOf ?cat .
            FILTER(?subClass != ?cat)
        }
        
        # 🟢 3. กันเหนียว ตัด ex:Exercise และ owl:Nothing ออก
        FILTER(?cat NOT IN (ex:Exercise, owl:Nothing))
        
        OPTIONAL { ?cat rdfs:label ?label . }
    }
    ORDER BY ?label ?cat
    """
    try:
        sparql_read.setQuery(query)
        sparql_read.setReturnFormat(JSON)
        results = sparql_read.query().convert()

        categories = []
        for r in results["results"]["bindings"]:
            cat_uri = r["cat"]["value"]
            cat_id = cat_uri.split("#")[-1] if "#" in cat_uri else cat_uri.split("/")[-1]
            label_val = r.get("label", {}).get("value", cat_id)

            categories.append({
                "id": cat_id,
                "name": label_val
            })

        return categories
    except Exception as e:
        print(f"❌ Error in get_all_categories_for_dropdown: {e}")
        return []


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
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT (COUNT(DISTINCT ?exercise) AS ?count) WHERE {
        ?exercise rdf:type/rdfs:subClassOf* ex:Exercise .
    }
    """

    # 3. นับจำนวน "รายการบันทึกการแนะนำการออกกำลังกาย" ทั้งหมดที่เกิดขึ้นในระบบจริง
    query_recommendations = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT (COUNT(?exercise) AS ?count) WHERE {
        ?p ex:recommendedExercise ?exercise .
    }
    """

    query_rule = """
    PREFIX swrl: <http://www.w3.org/2003/11/swrl#>
    SELECT (COUNT(DISTINCT ?rule) AS ?count) 
    WHERE {
        ?rule a swrl:Imp .
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

        sparql.setQuery(query_rule)
        res_r = sparql.query().convert()
        stats["total_rules"] = int(res_r["results"]["bindings"][0]["count"]["value"])

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
        sparql_write_client = SPARQLWrapper(GRAPHDB_WRITE)
        base_prefix = "http://example.org/diabetes#"
        
        final_id = existing_id if existing_id else f"17{random.randint(100, 999)}"
        subject_uri = f"<{base_prefix}{final_id}>"
        
        # URI ของ Class ย่อยที่เลือก (เช่น ex:Walking)
        class_uri = f"ex:{exercise_type}"

        insert_query = f"""
        PREFIX ex: <{base_prefix}>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        INSERT DATA {{
            {subject_uri} rdf:type owl:NamedIndividual .
            {subject_uri} rdf:type ex:Exercise .
            {subject_uri} rdf:type {class_uri} .                  # 🟢 เพิ่ม Class ย่อยตรงนี้
            
            {subject_uri} ex:hasKindOfExercise {class_uri} . # 🟢 เพิ่ม Object Property ตรงนี้
            {subject_uri} rdfs:label "{name}" .
            {subject_uri} ex:metValue "{float(mets)}"^^xsd:decimal .
            {subject_uri} ex:hasYoutubeID "{youtube_id if youtube_id else ''}" .
        }}
        """

        sparql_write_client.setQuery(insert_query)
        sparql_write_client.setMethod('POST')
        sparql_write_client.query()

        print(f"💾 [GraphDB] ซิงค์ข้อมูล ID #{final_id} (Type: {exercise_type}) เรียบร้อยแล้ว")
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
        return {"success": True, "message": "ลบข้อมูลสำกำดเร็จ"}
    except Exception as e:
        print(f"❌ Error deleting exercise: {e}")
        return {"success": False, "message": str(e)}

def get_all_categories_from_ontology():
    """
    ดึงเฉพาะหมวดหมู่สาย Exercise เท่านั้น 
    ตัดสาย KindOfExercise และคลาสย่อที่ซ้ำซ้อนออก
    """
    sparql = SPARQLWrapper(GRAPHDB_READ)
    category_map = {}

    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX ex: <http://example.org/diabetes#>

    SELECT DISTINCT ?cat ?label ?parent WHERE {
        # ดึงเฉพาะคลาสที่เป็น SubClass ของ Exercise เท่านั้น
        ?cat rdfs:subClassOf* ex:Exercise .
        
        OPTIONAL { ?cat rdfs:subClassOf ?parent . }
        OPTIONAL { ?cat rdfs:label ?label . }
        
        FILTER(STRSTARTS(STR(?cat), "http://example.org/diabetes#"))
    }
    """
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()

        # รายชื่อ Class ระบบ และ Class สาย KindOfExercise ที่ต้องการตัดออก
        ignore_classes = {
            "Exercise", "KindOfExercise", "Resource", "Resource",
            "WBearingAerobicExercise", "NWBearingAerobicExercise", # ตัดตัวย่อซ้ำซ้อน
            "ResistanceAndStretchingExercise",
            "Patient", "Disease", "Comorbidity", "Complication", 
            "LabExam", "PhysicalExam", "Symptom", "DiabeteType", 
            "Intensity", "Frequency", "PatientWarning", "WarningAvoidExercise",
            "WeeklyPlan", "DailyPlan", "MonthlyPlan", "ExercisePlan"
        }

        for row in results["results"]["bindings"]:
            cat_uri = row["cat"]["value"]
            cat_id = cat_uri.split("#")[-1] if "#" in cat_uri else cat_uri.split("/")[-1]

            if cat_id in ignore_classes:
                continue

            parent_uri = row.get("parent", {}).get("value", "")
            parent_id = parent_uri.split("#")[-1] if "#" in parent_uri else (parent_uri.split("/")[-1] if parent_uri else "")

            # กำหนด Parent เริ่มต้นถ้าชี้ไปหา Exercise หรือ Resource
            if parent_id in ["Exercise", "Resource", "owl:Thing", ""] or parent_id == cat_id:
                parent_id = "ExerciseCategory"

            label_val = row.get("label", {}).get("value", cat_id)

            if cat_id not in category_map:
                category_map[cat_id] = {
                    "category_id": cat_id,
                    "label_th": label_val if label_val else cat_id,
                    "parent_id": parent_id
                }
            else:
                if parent_id != "ExerciseCategory":
                    category_map[cat_id]["parent_id"] = parent_id

    except Exception as e:
        print("❌ [Admin Error] ดึงข้อมูลหมวดหมู่ล้มเหลว:", e)

    return list(category_map.values())

def update_category_hierarchy_in_ontology(category_id, parent_category_id=None, label_th=None):
    try:
        sparql_write_client = SPARQLWrapper(GRAPHDB_WRITE)
        base_prefix = "http://example.org/diabetes#"
        category_uri = f"<{base_prefix}{category_id}>"

        parent_to_group_map = {
            "WeightBearingAerobicExercise": "WBearingAerobicExercise",
            "WeightBearingAerobicSport": "WBearingAerobicExercise",
            "WBearingAerobicExercise": "WBearingAerobicExercise",
            "Running": "WBearingAerobicExercise",
            "Dancing": "WBearingAerobicExercise",
            "Walking": "WBearingAerobicExercise",

            "NonWeightBearingAerobicExercise": "NWBearingAerobicExercise",
            "NonWeightBearingAerobicSport": "NWBearingAerobicExercise",
            "NWBearingAerobicExercise": "NWBearingAerobicExercise",
            "WaterActivity": "NWBearingAerobicExercise",
            "Bicycling": "NWBearingAerobicExercise",

            "WeightBearingResistanceExercise": "ResistanceAndStretchingExercise",
            "NonWeightBearingResistanceExercise": "ResistanceAndStretchingExercise",
            "StretchingExercise": "ResistanceAndStretchingExercise",
            "ResistanceAndStretchingExercise": "ResistanceAndStretchingExercise"
        }

        # 🟢 1. จัดเตรียม Dynamic Triples ให้ถูก Syntax
        target_group_short = parent_to_group_map.get(
            parent_category_id, 
            parent_category_id if parent_category_id else "KindOfExercise"
        )
        group_triple = f"{category_uri} rdf:type ex:{target_group_short} ." if target_group_short else ""
        
        parent_triple = f"{category_uri} rdfs:subClassOf <{base_prefix}{parent_category_id}> ." if parent_category_id else ""
        label_triple = f'{category_uri} rdfs:label "{label_th}"@th .' if label_th else ""

        # 🟢 2. SPARQL Update ที่ใช้รูปแบบ DELETE ... INSERT ... WHERE ... (ไม่มีเครื่องหมาย ; คั่นกลาง)
        update_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX ex: <{base_prefix}>

        DELETE {{
            {category_uri} rdfs:subClassOf ?oldParent .
            {category_uri} rdf:type ?oldGroupType .
            {" " + category_uri + " rdfs:label ?oldLabel ." if label_th else ""}
        }}
        INSERT {{
            {category_uri} rdf:type owl:Class .
            {category_uri} rdf:type owl:NamedIndividual .
            {category_uri} rdf:type ex:KindOfExercise .
            {parent_triple}
            {group_triple}
            {label_triple}
        }}
        WHERE {{
            OPTIONAL {{
                {category_uri} rdfs:subClassOf ?oldParent .
                FILTER(?oldParent != rdfs:Resource)
            }}
            OPTIONAL {{
                {category_uri} rdf:type ?oldGroupType .
                FILTER(?oldGroupType NOT IN (ex:KindOfExercise, owl:Class, owl:NamedIndividual))
                FILTER(STRSTARTS(STR(?oldGroupType), "{base_prefix}"))
            }}
            {" OPTIONAL { " + category_uri + " rdfs:label ?oldLabel . }" if label_th else ""}
        }}
        """

        sparql_write_client.setQuery(update_query)
        sparql_write_client.setMethod('POST')
        sparql_write_client.query()

        print(f"✏️ [GraphDB Success] อัปเดต '{category_id}' สำเร็จ")
        return {"success": True, "message": "อัปเดตสายตระกูลหมวดหมู่สำเร็จ"}

    except Exception as e:
        print(f"❌ Error updating category hierarchy: {e}")
        return {"success": False, "message": str(e)}

def delete_category_from_ontology(category_id):
    """
    ลบหมวดหมู่ พร้อมกวาดลบ "ท่าออกกำลังกายทั้งหมด" ที่อยู่ในหมวดหมู่นั้นด้วย
    """
    sparql = SPARQLWrapper(GRAPHDB_WRITE)
    base_prefix = "http://example.org/diabetes#"
    
    query = f"""
    PREFIX ex: <{base_prefix}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    DELETE {{
        # 1. ลบข้อมูลของตัวหมวดหมู่เอง
        ex:{category_id} ?p1 ?o1 .
        ?s1 ?p2 ex:{category_id} .

        # 2. ลบข้อมูลของท่าออกกำลังกายที่อยู่ในหมวดหมู่นี้
        ?exercise ?p3 ?o3 .
        ?s4 ?p4 ?exercise .
    }}
    WHERE {{
        # 🔒 ตรวจสอบว่าหมวดหมู่นี้เป็นคลาสภายใต้ ex:Exercise
        ex:{category_id} rdfs:subClassOf* ex:Exercise .

        {{
            # ดึงข้อมูลของหมวดหมู่
            ex:{category_id} ?p1 ?o1 .
        }} UNION {{
            ?s1 ?p2 ex:{category_id} .
        }} UNION {{
            # ดึงท่าออกกำลังกายที่เป็นสมาชิกของหมวดหมู่นี้ (ทั้งแบบ Instance และ Subclass)
            ?exercise (rdf:type|rdfs:subClassOf) ex:{category_id} .
            
            {{ ?exercise ?p3 ?o3 . }}
            UNION
            {{ ?s4 ?p4 ?exercise . }}
        }}
    }}
    """
    try:
        sparql.setQuery(query)
        sparql.setMethod('POST')
        sparql.query()
        return {"success": True, "message": f"ลบหมวดหมู่ {category_id} และท่าออกกำลังกายภายในทั้งหมดเรียบร้อยแล้ว"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def get_frequencies():
    sparql = SPARQLWrapper(GRAPHDB_READ)
    query = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?freqURI ?label ?description WHERE {
        ?freqURI a ex:Frequency .
        OPTIONAL { ?freqURI rdfs:label ?label . }
        OPTIONAL { ?freqURI ex:description ?description . } 
    }
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    
    freq_list = []
    for row in results["results"]["bindings"]:
        uri = row["freqURI"]["value"]
        name = uri.split("#")[-1] # ได้เป็น Freq1, Freq2
        label = row.get("label", {}).get("value", name)
        description = row.get("description", {}).get("value", "")
        
        freq_list.append({
            "uri": uri, 
            "freq_id": name,         # ตั้งชื่อให้ตรงกับหน้า HTML Admin
            "label": label, 
            "description": description
        })

    # เรียงลำดับ Freq1, Freq2, Freq3...
    freq_list.sort(key=lambda x: int(''.join(filter(str.isdigit, x['freq_id'])) or 0))
    return {"success": True, "data": freq_list}

def save_or_update_frequency(freq_id, description=""):
    try:
        sparql = SPARQLWrapper(GRAPHDB_WRITE)
        query = f"""
        PREFIX ex: <http://example.org/diabetes#>

        DELETE {{
            ex:{freq_id} ex:description ?oldDesc .
        }}
        WHERE {{
            OPTIONAL {{ ex:{freq_id} ex:description ?oldDesc . }}
        }} ;

        INSERT DATA {{
            ex:{freq_id} a ex:Frequency ;
                        ex:description "{description}" .
        }}
        """
        sparql.setMethod(POST)
        sparql.setQuery(query)
        sparql.query()
        return {"success": True, "message": f"บันทึกข้อมูล ex:{freq_id} เรียบร้อยแล้ว"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    
# 3. ฟังก์ชันลบข้อมูล Frequency
# 3. ฟังก์ชันลบข้อมูล Frequency
def delete_frequency(freq_id):
    try:
        sparql = SPARQLWrapper(GRAPHDB_WRITE)
        query = f"""
        PREFIX ex: <http://example.org/diabetes#>

        DELETE {{
            # 1. ลบ Properties ทั้งหมดของ freq_id นี้
            ex:{freq_id} ?p1 ?o1 .
            # 2. ลบความสัมพันธ์ที่โหนดอื่นชี้มาหา freq_id นี้
            ?s2 ?p2 ex:{freq_id} .
        }}
        WHERE {{
            # 🔒 ล็อคเงื่อนไข: ต้องเป็นประเภท Frequency เท่านั้นถึงจะทำการลบ
            ex:{freq_id} a ex:Frequency .

            # ดึงความสัมพันธ์ทั้งหมดที่ออกไป และชี้เข้ามา
            {{
                ex:{freq_id} ?p1 ?o1 .
            }}
            UNION
            {{
                ?s2 ?p2 ex:{freq_id} .
            }}
        }}
        """
        sparql.setMethod(POST)
        sparql.setQuery(query)
        sparql.query()
        return {"success": True, "message": f"ลบข้อมูล ex:{freq_id} เรียบร้อยแล้ว"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    
def get_avoidance_page():
    sparql = SPARQLWrapper(GRAPHDB_READ)
    
    # ใช้ SPARQL ค้นหา Class ที่มีคำว่า WarningAvoidExercise โดยไม่ต้องฟิกซ์ PREFIX ทั้งหมด
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?subject ?description WHERE {
        ?subject rdf:type ?type .
        FILTER(STRENDS(STR(?type), "WarningAvoidExercise"))
        OPTIONAL { 
            ?subject ?p ?description .
            FILTER(STRENDS(STR(?p), "description"))
        }
    }
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    
    avoids = []
    for row in results["results"]["bindings"]:
        uri = row["subject"]["value"]
        name = uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
        description = row.get("description", {}).get("value", "")
        
        avoids.append({
            "id": name,
            "description": description
        })

    avoids.sort(key=lambda x: int(''.join(filter(str.isdigit, x['id'])) or 0))

    return {"success": True, "data": avoids}

def save_or_update_avoidance(avoid_id, description=""):
    try:
        sparql = SPARQLWrapper(GRAPHDB_WRITE)
        
        # 🟢 ปรับ PREFIX และ Class name ให้ตรงกับ WarningAvoidExercise
        query = f"""
        PREFIX ex: <http://www.owl-ontologies.com/Ontology1732684725.owl#>

        DELETE {{
            ex:{avoid_id} ex:description ?oldDesc .
        }}
        WHERE {{
            OPTIONAL {{ ex:{avoid_id} ex:description ?oldDesc . }}
        }} ;

        INSERT DATA {{
            ex:{avoid_id} a ex:WarningAvoidExercise ;
                        ex:description "{description}" .
        }}
        """
        sparql.setMethod(POST)
        sparql.setQuery(query)
        sparql.query()
        return {"success": True, "message": f"บันทึกข้อมูล ex:{avoid_id} เรียบร้อยแล้ว"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    
def delete_avoidance(avoid_id):
    sparql = SPARQLWrapper(GRAPHDB_WRITE)
    sparql.setMethod(POST)

    query = f"""
    PREFIX ex: <http://www.owl-ontologies.com/Ontology1732684725.owl#>

    DELETE {{
        # 1. ลบ Properties ทั้งหมดของ avoid_id นี้
        ex:{avoid_id} ?p1 ?o1 .
        # 2. ลบความสัมพันธ์ที่โหนดอื่นชี้มาหา avoid_id นี้
        ?s2 ?p2 ex:{avoid_id} .
    }}
    WHERE {{
        # 🔒 ล็อคเงื่อนไข: ต้องเป็นประเภท WarningAvoidExercise เท่านั้นถึงจะทำการลบ
        ex:{avoid_id} a ex:WarningAvoidExercise .

        # ดึงความสัมพันธ์ทั้งหมดที่ออกไป และชี้เข้ามา
        {{
            ex:{avoid_id} ?p1 ?o1 .
        }}
        UNION
        {{
            ?s2 ?p2 ex:{avoid_id} .
        }}
    }}
    """
    sparql.setQuery(query)
    try:
        sparql.query()
        return {"success": True, "message": f"ลบข้อมูลข้อควรระวัง ex:{avoid_id} สำเร็จ"}
    except Exception as e:
        return {"success": False, "message": str(e)}

def get_patient_warning():
    sparql = SPARQLWrapper(GRAPHDB_READ)
    
    # ใช้ SPARQL ค้นหา Class ที่มีคำว่า WarningAvoidExercise โดยไม่ต้องฟิกซ์ PREFIX ทั้งหมด
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT ?subject ?description WHERE {
        ?subject rdf:type ?type .
        FILTER(STRENDS(STR(?type), "PatientWarning"))
        OPTIONAL { 
            ?subject ?p ?description .
            FILTER(STRENDS(STR(?p), "description"))
        }
    }
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    
    warning = []
    for row in results["results"]["bindings"]:
        uri = row["subject"]["value"]
        name = uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
        description = row.get("description", {}).get("value", "")
        
        warning.append({
            "id": name,
            "description": description
        })

    warning.sort(key=lambda x: int(''.join(filter(str.isdigit, x['id'])) or 0))

    return {"success": True, "data": warning}

def save_or_update_warning(warning_id, description=""):
    try:
        sparql = SPARQLWrapper(GRAPHDB_WRITE)
        sparql.setMethod(POST)
        
        # 🟢 ปรับ PREFIX และ Class name ให้ตรงrกับ WarningAvoidExercise
        query = f"""
        PREFIX ex: <http://www.owl-ontologies.com/Ontology1732684725.owl#>

        DELETE {{
            ex:{warning_id} ex:description ?oldDesc .
        }}
        WHERE {{
            OPTIONAL {{ ex:{warning_id} ex:description ?oldDesc . }}
        }} ;

        INSERT DATA {{
            ex:{warning_id} a ex:PatientWarning;
                        ex:description "{description}" .
        }}
        """
        sparql.setMethod(POST)
        sparql.setQuery(query)
        sparql.query()
        return {"success": True, "message": f"บันทึกข้อมูล ex:{warning_id} เรียบร้อยแล้ว"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    
def delete_warning(warning_id):
    sparql = SPARQLWrapper(GRAPHDB_WRITE)
    sparql.setMethod(POST)

    query = f"""
    PREFIX ex: <http://www.owl-ontologies.com/Ontology1732684725.owl#>

    DELETE {{
        # 1. ลบ Properties ทั้งหมดของ warning_id นี้
        ex:{warning_id} ?p1 ?o1 .
        # 2. ลบความสัมพันธ์ที่โหนดอื่นชี้มาหา warning_id นี้
        ?s2 ?p2 ex:{warning_id} .
    }}
    WHERE {{
        # 🔒 เงื่อนไขสำคัญ: เช็กก่อนว่า ex:{warning_id} เป็น PatientWarning จริงหรือไม่
        ex:{warning_id} a ex:PatientWarning .

        # ดึงความสัมพันธ์ทั้งหมดที่ออกไป และชี้เข้ามา
        {{
            ex:{warning_id} ?p1 ?o1 .
        }}
        UNION
        {{
            ?s2 ?p2 ex:{warning_id} .
        }}
    }}
    """
    sparql.setQuery(query)
    try:
        sparql.query()
        return {"success": True, "message": f"ลบข้อมูลคำเตือน ex:{warning_id} ทั้งหมดสำเร็จ"}
    except Exception as e:
        return {"success": False, "message": str(e)}