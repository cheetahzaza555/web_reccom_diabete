from SPARQLWrapper import SPARQLWrapper, JSON, POST
import rules

# ตั้งค่า GraphDB
DB_URL = "http://localhost:7200/repositories/Project"
UPDATE_URL = DB_URL + "/statements"

sparql_read = SPARQLWrapper(DB_URL)
sparql_read.setReturnFormat(JSON)

sparql_write = SPARQLWrapper(UPDATE_URL)
sparql_write.setMethod(POST)

def add_new_patient(data):
    """เพิ่มผู้ป่วยใหม่ลงฐานข้อมูล"""
    new_id = f"Patient{data['id']}"
    
    fname = data.get('firstname', '-')
    lname = data.get('lastname', '-')
    sbp = data.get('sbp', '0')
    dbp = data.get('dbp', '0')
    chol = data.get('chol', '0')
    ldl = data.get('ldl', '0')
    hdl = data.get('hdl', '0')
    tri = data.get('tri', '0')

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
    
    print(f"💾 บันทึกผู้ป่วย {new_id} เสร็จสิ้น")
    print(f"   - BMI: {data['bmi']}, SBP: {sbp}, DBP: {dbp}")
    print(f"   - Chol: {chol}, LDL: {ldl}")
    
    # รันกฎ
    run_inference_engine()
    
    # ตรวจสอบผลลัพธ์ทันทีหลังรันกฎ
    verify_patient_data(new_id)
    
    return new_id

def run_inference_engine():
    """สั่งรันกฎทั้งหมดตามลำดับ"""
    print("\n🧠 Services: กำลังประมวลผลกฎ...")
    
    # 1. ลบข้อมูลเก่า
    print("   1️⃣ ลบข้อมูลเก่า...")
    sparql_write.setQuery(rules.DELETE_OLD_DATA)
    sparql_write.query()
    
    # 2. รันกฎวินิจฉัย
    print("   2️⃣ รันกฎวินิจฉัย...")
    for i, rule in enumerate(rules.DIAGNOSIS_RULES, 1):
        sparql_write.setQuery(rule)
        sparql_write.query()
        print(f"      ✓ กฎวินิจฉัยที่ {i} เสร็จสิ้น")
    
    # 3. รันกฎแนะนำ
    print("   3️⃣ รันกฎแนะนำ...")
    for i, rule in enumerate(rules.RECOMMENDATION_RULES, 1):
        sparql_write.setQuery(rule)
        sparql_write.query()
        print(f"      ✓ กฎแนะนำที่ {i} เสร็จสิ้น")
    
    print("✅ Services: ประมวลผลเสร็จสิ้น\n")

def verify_patient_data(patient_id):
    """ตรวจสอบข้อมูลที่ถูกสร้างจากกฎ (Debug)"""
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?comorbidity ?warning ?exercise
    WHERE {{
        OPTIONAL {{ ex:{patient_id} ex:hasComorbidity ?comorbidity }}
        OPTIONAL {{ ex:{patient_id} ex:hasPatientWarning ?warning }}
        OPTIONAL {{ ex:{patient_id} ex:recommendedExercise ?exercise }}
    }}
    """
    sparql_read.setQuery(query)
    results = sparql_read.query().convert()
    
    print(f"🔍 ตรวจสอบข้อมูลผู้ป่วย {patient_id}:")
    bindings = results['results']['bindings']
    
    if not bindings or not any(bindings[0].values()):
        print("   ⚠️ ไม่พบข้อมูลที่ถูกสร้างจากกฎ! กฎอาจไม่ทำงาน")
        return
    
    for r in bindings:
        if 'comorbidity' in r:
            print(f"   ✓ Comorbidity: {r['comorbidity']['value']}")
        if 'warning' in r:
            print(f"   ✓ Warning: {r['warning']['value']}")
        if 'exercise' in r:
            print(f"   ✓ Exercise: {r['exercise']['value']}")

def get_patient_results(patient_id):
    """ดึงผลลัพธ์จาก DB พร้อมข้อความบรรยาย"""
    print(f"\n📊 กำลังดึงผลลัพธ์สำหรับ {patient_id}...")
    
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?exerciseName ?warningDesc
    WHERE {{
        OPTIONAL {{
            ex:{patient_id} ex:recommendedExercise ?rec .
            ?rec rdfs:label ?exerciseName . 
        }}
        
        OPTIONAL {{ 
            ex:{patient_id} ex:hasPatientWarning ?warning .
            ?warning ex:description ?warningDesc . 
        }}
    }}
    """
    
    print(f"🔍 SPARQL Query:\n{query}\n")
    
    sparql_read.setQuery(query)
    results = sparql_read.query().convert()
    
    # แสดงผลลัพธ์ดิบ
    print(f"📦 Raw Results: {results['results']['bindings']}\n")
    
    exercises = set()
    warnings = set()
    
    for r in results['results']['bindings']:
        if 'exerciseName' in r:
            exercises.add(r['exerciseName']['value'])
            print(f"   ✓ พบท่าออกกำลังกาย: {r['exerciseName']['value']}")
            
        if 'warningDesc' in r:
            warnings.add(r['warningDesc']['value'])
            print(f"   ✓ พบคำเตือน: {r['warningDesc']['value']}")
    
    exercise_list = list(exercises)[:5]
    warning_list = list(warnings)
    
    print(f"\n📋 สรุปผลลัพธ์:")
    print(f"   - ท่าออกกำลังกาย: {len(exercise_list)} ท่า")
    print(f"   - คำเตือน: {len(warning_list)} ข้อ\n")
    
    return exercise_list, warning_list

def get_patient_profile(id_input):
    """ดึงข้อมูลส่วนตัวของผู้ป่วย"""
    potential_ids = [f"Patient{id_input}"]
    
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
            data = bindings[0]
            return {
                "found_id": pid,
                "firstname": data.get("fname", {}).get("value", "-"),
                "lastname": data.get("lname", {}).get("value", "-"),
                "type": data.get("dtype", {}).get("value", "-"),
                "bmi": data.get("bmi", {}).get("value", "-"),
                "sbp": data.get("sbp", {}).get("value", "-"),
                "dbp": data.get("dbp", {}).get("value", "-"),
                "chol": data.get("chol", {}).get("value", "-"),
                "ldl": data.get("ldl", {}).get("value", "-"),
            }
            
    return None

def delete_patient_by_id(patient_id_num):
    """ลบข้อมูลผู้ป่วยทั้งหมด"""
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

def run_inference_for_all_patients():
    """รันกฎสำหรับผู้ป่วยทั้งหมดที่มีอยู่ใน GraphDB"""
    print("\n🔄 กำลังรันกฎสำหรับผู้ป่วยทั้งหมด...")
    
    # เรียกใช้ฟังก์ชันรันกฎปกติ (มันจะรันกฎกับทุกคนที่มี Patient Class)
    run_inference_engine()
    
    # นับจำนวนผู้ป่วยที่ได้รับการประมวลผล
    query = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT (COUNT(DISTINCT ?p) as ?count)
    WHERE {
        ?p a ex:Patient .
    }
    """
    sparql_read.setQuery(query)
    results = sparql_read.query().convert()
    count = results['results']['bindings'][0]['count']['value']
    
    print(f"✅ ประมวลผลเสร็จสิ้น - ผู้ป่วยทั้งหมด: {count} คน\n")
    return int(count)