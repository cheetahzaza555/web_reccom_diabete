from SPARQLWrapper import SPARQLWrapper, JSON
from modules.config import GRAPHDB_READ

def get_admin_dashboard_stats():
    """ ฟังก์ชันดึงตัวเลขสถิติแยกคิวรี เพื่อความแม่นยำ 100% ไม่เกิดการคูณซ้ำ """
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
        
        # คิวรีจำนวนคนไข้
        sparql.setQuery(query_patients)
        res_p = sparql.query().convert()
        stats["total_patients"] = int(res_p["results"]["bindings"][0]["count"]["value"])
        
        # คิวรีจำนวนท่าออกกำลังกาย
        sparql.setQuery(query_exercises)
        res_e = sparql.query().convert()
        stats["total_exercises"] = int(res_e["results"]["bindings"][0]["count"]["value"])
        
        # คิวรีจำนวนรายการแนะนำทั้งหมด
        sparql.setQuery(query_recommendations)
        res_r = sparql.query().convert()
        stats["total_mets"] = int(res_r["results"]["bindings"][0]["count"]["value"])
        
    except Exception as e:
        print("❌ [Admin Module Error] เกิดข้อผิดพลาดขณะ Query สถิติรวม:", e)
        
    return stats

def get_recent_registered_users():
    """ ดึงรายชื่อผู้ป่วยที่ลงทะเบียนในระบบมาแสดงในตารางกิจกรรมล่าสุด """
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
            # ดึงข้อมูลและกำหนดค่า Default เผื่อกรณีข้อมูลในคลังไม่ครบถ้วน
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

def get_all_patients_management():
    """ ดึงรายชื่อผู้ป่วยทุกคนพร้อมรายละเอียดสําคัญมาแสดงในตารางจัดการข้อมูล """
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
        
        # ดึงค่าแล็บและผลร่างกายเบื้องต้นมาโชว์ในตารางด้วย
        OPTIONAL { ?p ex:hasPhysicalExam ?pe . OPTIONAL { ?pe ex:hasBMI ?bmi } }
        OPTIONAL { ?p ex:hasLabExam ?le . OPTIONAL { ?le ex:hasFPG ?fpg } }
    }
    """
    try:
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        
        for row in results["results"]["bindings"]:
            # แกะ ID ผู้ป่วยออกมาจาก URI (เช่น http://example.org/diabetes#Patient01 -> Patient01)
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