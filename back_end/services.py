# services.py
from SPARQLWrapper import SPARQLWrapper, JSON, POST
import rules  # <--- นำเข้ากฎจากไฟล์ rules.py

# ตั้งค่า GraphDB ตรงนี้จุดเดียว
DB_URL = "http://localhost:7200/repositories/Project"
UPDATE_URL = DB_URL + "/statements"

sparql_read = SPARQLWrapper(DB_URL)
sparql_read.setReturnFormat(JSON)

sparql_write = SPARQLWrapper(UPDATE_URL)
sparql_write.setMethod(POST)

def add_new_patient(data):
    run_inference_engine()
    """เพิ่มผู้ป่วยใหม่ลงฐานข้อมูล (รับค่าครบถ้วน)"""
    new_id = f"Patient{data['id']}" # สร้าง ID เช่น Patient99
    
    # 1. ดึงค่าต่างๆ มาเตรียมไว้ (ถ้าไม่มีให้ใส่เป็น 0 หรือ -)
    # ต้องรับค่า SBP, DBP, Chol ฯลฯ ด้วย ไม่อย่างนั้นกฎ SWRL จะไม่ทำงาน
    fname = data.get('firstname', '-')
    lname = data.get('lastname', '-')
    sbp = data.get('sbp', '0')
    dbp = data.get('dbp', '0')
    chol = data.get('chol', '0')
    ldl = data.get('ldl', '0')
    hdl = data.get('hdl', '0')
    tri = data.get('tri', '0')

    # 2. เตรียมคำสั่ง INSERT (ใส่ข้อมูลให้ครบทุก field)
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT DATA {{
        ex:{new_id} a ex:Patient ;
                    ex:firstname "{fname}" ;
                    ex:lastname "{lname}" ;
                    ex:diabetType ex:{data['type']} ;
                    ex:hasPhysicalExam ex:{new_id}_PE ;
                    ex:hasLabExam ex:{new_id}_LE .
        
        ex:{new_id}_PE a ex:PhysicalExam ;
                       ex:hasBMI "{data['bmi']}"^^xsd:decimal ;
                       ex:hasSBP "{sbp}"^^xsd:decimal ;
                       ex:hasDBP "{dbp}"^^xsd:decimal .
                       
        ex:{new_id}_LE a ex:LabExam ;
                       ex:hasTotalCholesterol "{chol}"^^xsd:decimal ;
                       ex:hasLDL "{ldl}"^^xsd:decimal ;
                       ex:hasHDL "{hdl}"^^xsd:decimal ;
                       ex:hasTriglyceride "{tri}"^^xsd:decimal .
    }}
    """
    sparql_write.setQuery(query)
    sparql_write.query()
    
    # 3. [สำคัญ] สั่งรันกฎทันทีหลังจากเพิ่มข้อมูลเสร็จ
    print(f"💾 บันทึกผู้ป่วย {new_id} เสร็จสิ้น -> กำลังสั่งรันกฎ...")
    run_inference_engine()
    
    return new_id

def run_inference_engine():
    """สั่งรันกฎทั้งหมดตามลำดับ"""
    print("🧠 Services: กำลังประมวลผลกฎ...")
    
    sparql_write.setQuery(rules.DELETE_OLD_DATA)
    sparql_write.query()
    
    # 2. รันกฎวินิจฉัย
    sparql_write.setQuery(rules.RULE_DIAGNOSIS_NORMAL)
    sparql_write.query()
    
    # 3. รันกฎแนะนำ
    sparql_write.setQuery(rules.RULE_RECOMMENDATION)
    sparql_write.query()
    
    print("✅ Services: ประมวลผลเสร็จสิ้น")

def get_patient_results(patient_id):
    """ดึงผลลัพธ์จาก DB พร้อมข้อความบรรยาย"""
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?exerciseName ?warningDesc
    WHERE {{
        # 1. ดึงท่าออกกำลังกาย (แก้ชื่อ Property ตรงนี้)
        OPTIONAL {{
            ex:{patient_id} ex:recommendedExercise ?rec .  # <--- แก้เป็น recommendedExercise
            ?rec rdfs:label ?exerciseName . 
        }}
        
        # 2. ดึงคำเตือน (เหมือนเดิม)
        OPTIONAL {{ 
            ex:{patient_id} ex:hasPatientWarning ?warning .
            ?warning ex:description ?warningDesc . 
        }}
    }}
    """
    sparql_read.setQuery(query)
    results = sparql_read.query().convert()
    
    # จัด Format ข้อมูล
    exercises = set()
    warnings = set()
    
    for r in results['results']['bindings']:
        # เก็บชื่อท่าออกกำลังกาย
        if 'exerciseName' in r:
            exercises.add(r['exerciseName']['value'])
            
        # เก็บข้อความคำเตือน (ภาษาไทย)
        if 'warningDesc' in r:
            warnings.add(r['warningDesc']['value'])
            
    exercise_list = list(exercises)
    warning_list = list(warnings)
            
    limited_exercises = exercise_list[:5]
    
    return limited_exercises, warning_list

def get_patient_profile(id_input):
    """ดึงข้อมูลส่วนตัวของผู้ป่วย (ชื่อ, BMI, ผลเลือด)"""
    
    # หมายเหตุ: ตรงนี้ต้องระวังเรื่องชื่อ ID
    # ถ้าเป็นคนที่เราเพิ่งเพิ่มใหม่ ID จะชื่อ "Patient_99"
    # แต่ถ้าเป็นคนเก่าในไฟล์ Patient3.ttl ชื่ออาจจะเป็น "Patient1"
    # เพื่อความชัวร์ เราจะลองหาทั้ง 2 แบบ
    
    potential_ids = [f"Patient_{id_input}", f"Patient{id_input}"] 
    
    for pid in potential_ids:
        query = f"""
        PREFIX ex: <http://example.org/diabetes#>
        SELECT ?fname ?lname ?dtype ?bmi ?sbp ?dbp ?chol ?ldl
        WHERE {{
            ex:{pid} a ex:Patient .
            OPTIONAL {{ ex:{pid} ex:firstname ?fname }}
            OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
            OPTIONAL {{ ex:{pid} ex:diabetType ?dtype }}
            
            OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe .
                        ?pe ex:hasBMI ?bmi ;
                            ex:hasSBP ?sbp ;
                            ex:hasDBP ?dbp . }}
                        
            OPTIONAL {{ ex:{pid} ex:hasLabExam ?le .
                        ?le ex:hasTotalCholesterol ?chol ;
                            ex:hasLDL ?ldl . }}
        }}
        """
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()
        bindings = results["results"]["bindings"]
        
        if bindings:
            # ถ้าเจอข้อมูล ให้ return ทันที
            data = bindings[0]
            return {
                "found_id": pid, # ส่ง ID ที่ถูกต้องกลับไป
                "firstname": data.get("fname", {}).get("value", "-"),
                "lastname": data.get("lname", {}).get("value", "-"),
                "type": data.get("dtype", {}).get("value", "-"),
                "bmi": data.get("bmi", {}).get("value", "-"),
                "sbp": data.get("sbp", {}).get("value", "-"),
                "dbp": data.get("dbp", {}).get("value", "-"),
                "chol": data.get("chol", {}).get("value", "-"),
                "ldl": data.get("ldl", {}).get("value", "-"),
            }
            
    return None # ไม่เจอเลย

def delete_patient_by_id(patient_id_num):
    # แก้ตรงนี้! ให้เหมือนกับตอน add (ไม่มี underscore)
    target_id = f"Patient{patient_id_num}" 
    
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    
    DELETE {{
        ex:{target_id} ?p ?o .
        ?pe ?p2 ?o2 .
        ?le ?p3 ?o3 .
    }}
    WHERE {{
        ex:{target_id} ?p ?o .
        OPTIONAL {{ ex:{target_id} ex:hasPhysicalExam ?pe . ?pe ?p2 ?o2 . }}
        OPTIONAL {{ ex:{target_id} ex:hasLabExam ?le . ?le ?p3 ?o3 . }}
    }}
    """
    sparql_write.setQuery(query)
    sparql_write.query()
    print(f"🗑️ ลบข้อมูล {target_id} เรียบร้อยแล้ว")