import io
import requests
import traceback
import sys
# 1. แก้ภาษาต่างดาวใน Terminal
sys.stdout.reconfigure(encoding='utf-8')

from SPARQLWrapper import SPARQLWrapper, JSON, POST
from owlready2 import *

# ==========================================
# 1. ตั้งค่าการเชื่อมต่อ
# ==========================================
REPO_NAME = "Project" 
GRAPHDB_BASE = "https://reynaldo-spookiest-phonogramically.ngrok-free.dev/repositories"
GRAPHDB_READ = f"{GRAPHDB_BASE}/{REPO_NAME}"
GRAPHDB_WRITE = f"{GRAPHDB_BASE}/{REPO_NAME}/statements"

sparql_read = SPARQLWrapper(GRAPHDB_READ)
sparql_read.setReturnFormat(JSON)
sparql_write = SPARQLWrapper(GRAPHDB_WRITE)
sparql_write.setMethod(POST)

# ==========================================
# 2. ฟังก์ชันโหลด Ontology
# ==========================================
def load_ontology_from_graphdb():
    print(f"🌍 กำลังดาวน์โหลดกฎและโครงสร้างจาก GraphDB ({REPO_NAME})...")
    headers = {"Accept": "text/plain"} 
    params = {"infer": "false"} 
    try:
        response = requests.get(f"{GRAPHDB_READ}/statements", headers=headers, params=params)
        response.raise_for_status()
        
        # Decode utf-8
        raw_data = response.content.decode('utf-8')
        clean_lines = [line for line in raw_data.splitlines() if "http://www.w3.org/2002/07/owl#imports" not in line]
        clean_data = "\n".join(clean_lines)
        
        onto = get_ontology("http://example.org/diabetes_from_db").load(fileobj=io.BytesIO(clean_data.encode('utf-8')), format="ntriples")
        print(f"✅ โหลดสำเร็จ! พบกฎ {len(list(onto.rules()))} ข้อ")
        return onto
    except Exception as e:
        print(f"❌ Error โหลดจาก GraphDB: {e}")
        return None

onto = load_ontology_from_graphdb()

if onto:
    # 2. กำหนด Namespace แบบ Fix ตายตัว (ไม่ให้มี #exercise# หลุดมา)
    ex = onto.get_namespace("http://example.org/diabetes#")
    
    with onto:
        class Patient(Thing): namespace = ex
        class PhysicalExam(Thing): namespace = ex
        class LabExam(Thing): namespace = ex
        class Exercise(Thing): namespace = ex
        class DiabetType(Thing): namespace = ex
        class PatientWarning(Thing): namespace = ex
        
        class hasBMI(DataProperty): namespace = ex; range = [float]
        class hasSBP(DataProperty): namespace = ex; range = [float]
        class hasDBP(DataProperty): namespace = ex; range = [float]
        class hasTotalCholesterol(DataProperty): namespace = ex; range = [float]
        class hasLDL(DataProperty): namespace = ex; range = [float]
        class hasHDL(DataProperty): namespace = ex; range = [float]
        class hasTriglyceride(DataProperty): namespace = ex; range = [float]
        
        class diabetType(ObjectProperty): namespace = ex; range = [DiabetType]
        class hasPhysicalExam(ObjectProperty): namespace = ex; range = [PhysicalExam]
        class hasLabExam(ObjectProperty): namespace = ex; range = [LabExam]
        class recommendedExercise(ObjectProperty): namespace = ex; range = [Exercise]
        class hasPatientWarning(ObjectProperty): namespace = ex; range = [PatientWarning]

def get_thai_text(entity):
    if hasattr(entity, "description") and entity.description: return str(entity.description[0])
    if hasattr(entity, "label") and entity.label: return str(entity.label[0])
    return entity.name

# ==========================================
# 4. ฟังก์ชันประมวลผล (Debug Mode)
# ==========================================
def process_patient_realtime(patient_id):
    if not onto: return [], ["Error: Ontology not loaded"]

    pid_db = f"Patient{patient_id}"
    pid_mem = f"Patient_Mem_{patient_id}"

    try:
        print(f"📥 ดึงข้อมูล {pid_db}...")
        query = f"""
        PREFIX ex: <http://example.org/diabetes#>
        SELECT ?type ?bmi ?sbp ?dbp ?chol ?ldl ?hdl ?tri
        WHERE {{
            ex:{pid_db} a ex:Patient ; ex:diabetType ?typeUri .
            OPTIONAL {{ ex:{pid_db} ex:hasPhysicalExam ?pe . OPTIONAL {{ ?pe ex:hasBMI ?bmi }} OPTIONAL {{ ?pe ex:hasSBP ?sbp }} OPTIONAL {{ ?pe ex:hasDBP ?dbp }} }}
            OPTIONAL {{ ex:{pid_db} ex:hasLabExam ?le . OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} OPTIONAL {{ ?le ex:hasHDL ?hdl }} OPTIONAL {{ ?le ex:hasTriglyceride ?tri }} }}
            BIND(STRAFTER(STR(?typeUri), "#") AS ?type)
        }}
        """
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()
        
        if not results["results"]["bindings"]:
            print(f"❌ ไม่พบข้อมูล {pid_db} ใน DB")
            return None, None

        row = results["results"]["bindings"][0]
        data = {
            'type': row.get('type', {}).get('value', 'T2DM'),
            'bmi': float(row.get('bmi', {}).get('value', 0.0)),
            'sbp': float(row.get('sbp', {}).get('value', 0.0)),
            'dbp': float(row.get('dbp', {}).get('value', 0.0)),
            'chol': float(row.get('chol', {}).get('value', 0.0)),
            'ldl': float(row.get('ldl', {}).get('value', 0.0)),
            'hdl': float(row.get('hdl', {}).get('value', 0.0)),
            'tri': float(row.get('tri', {}).get('value', 0.0))
        }
        
        print(f"🧐 ข้อมูลเตรียมสอบ: {data}")

        with onto:
            # ใช้ ex.Patient โดยตรง เพื่อบังคับ Namespace ให้ถูกต้อง
            p = ex.Patient(pid_mem)
            print(f"🔎 สร้างคนไข้ที่ IRI: {p.iri}") # <--- ต้องไม่มี #exercise# แล้วนะ

            target_type = data['type']
            # หา T1DM/T2DM จาก ex (http://example.org/diabetes#)
            type_obj = ex[target_type] 
            if not type_obj: 
                # ถ้าหาใน ex ไม่เจอ ลอง search ทั่วไป
                print(f"⚠️ หา {target_type} ใน ex ไม่เจอ ลอง search...")
                type_obj = onto.search_one(iri=f"*{target_type}")
                if not type_obj: type_obj = ex.DiabetType(target_type)

            p.diabetType = [type_obj]
                
            pe = ex.PhysicalExam(f"PE_Mem_{patient_id}")
            pe.hasBMI = [data['bmi']]
            pe.hasSBP = [data['sbp']]
            pe.hasDBP = [data['dbp']]
            p.hasPhysicalExam = [pe]
            
            le = ex.LabExam(f"LE_Mem_{patient_id}")
            le.hasTotalCholesterol = [data['chol']]
            le.hasLDL = [data['ldl']]
            le.hasHDL = [data['hdl']]
            le.hasTriglyceride = [data['tri']]
            p.hasLabExam = [le]

        print("🧠 กำลังรัน SWRL Reasoner...")
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

        # --- Debug Dump: ดูว่า Reasoner คิดอะไรออกมาบ้าง (ทุก Property) ---
        print("-" * 30)
        print("🕵️‍♀️ DEBUG: สิ่งที่ Reasoner คิดได้:")
        for prop in p.get_properties():
            print(f"   -> {prop.name}: {prop[p]}")
        print("-" * 30)

        # --- ดึงผลลัพธ์จริง ---
        recs = []
        warns = []
        save_recs_ids = []
        save_warns_ids = []

        if hasattr(p, "hasPatientWarning"):
             for w in p.hasPatientWarning:
                 warns.append(get_thai_text(w))
                 save_warns_ids.append(w.name)
                 
        if hasattr(p, "recommendedExercise"):
             for r in p.recommendedExercise:
                 recs.append(get_thai_text(r))
                 save_recs_ids.append(r.name)

        print(f"✅ ผลลัพธ์สรุป: {recs}, {warns}")
        
        save_results_to_db(patient_id, save_recs_ids, save_warns_ids)
        
        destroy_entity(p)
        destroy_entity(pe)
        if 'le' in locals(): destroy_entity(le)
        return recs, warns

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        traceback.print_exc()
        return [], [f"System Error: {str(e)}"]

def save_results_to_db(pid_num, recs, warns):
    pid = f"Patient{pid_num}"
    del_q = f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ex:{pid} ex:hasPatientWarning ?w . ex:{pid} ex:recommendedExercise ?r }} WHERE {{ OPTIONAL {{ ex:{pid} ex:hasPatientWarning ?w }} OPTIONAL {{ ex:{pid} ex:recommendedExercise ?r }} }}"
    sparql_write.setQuery(del_q); sparql_write.query()
    
    triples = ""
    for r in recs: triples += f"ex:{pid} ex:recommendedExercise ex:{r} .\n"
    for w in warns: triples += f"ex:{pid} ex:hasPatientWarning ex:{w} .\n"
    
    if triples:
        ins_q = f"PREFIX ex: <http://example.org/diabetes#> INSERT DATA {{ {triples} }}"
        sparql_write.setQuery(ins_q); sparql_write.query()
        print(f"💾 บันทึกผลลัพธ์ลง DB เรียบร้อย")

def get_patient_profile(patient_id):
    pid = f"Patient{patient_id}"
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?fname ?lname ?type ?bmi ?sbp ?dbp ?chol ?ldl ?recName ?warnDesc
    WHERE {{
        ex:{pid} a ex:Patient ; ex:diabetType ?typeUri .
        BIND(STRAFTER(STR(?typeUri), "#") AS ?type)
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }}
        OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
        OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . OPTIONAL {{ ?pe ex:hasBMI ?bmi }} OPTIONAL {{ ?pe ex:hasSBP ?sbp }} OPTIONAL {{ ?pe ex:hasDBP ?dbp }} }}
        OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} }}
        OPTIONAL {{ ex:{pid} ex:recommendedExercise ?rec . OPTIONAL {{ ?rec rdfs:label ?recLabel }} BIND(COALESCE(?recLabel, STRAFTER(STR(?rec), "#")) AS ?recName) }} 
        OPTIONAL {{ ex:{pid} ex:hasPatientWarning ?warn . OPTIONAL {{ ?warn ex:description ?wDesc }} OPTIONAL {{ ?warn rdfs:label ?wLabel }} BIND(COALESCE(?wDesc, ?wLabel, STRAFTER(STR(?warn), "#")) AS ?warnDesc) }}
    }}
    """
    sparql_read.setQuery(query)
    results = sparql_read.query().convert()
    bindings = results["results"]["bindings"]
    if not bindings: return None
    first = bindings[0]
    info = {
        "firstname": first.get("fname", {}).get("value", "-"),
        "lastname": first.get("lname", {}).get("value", "-"),
        "type": first.get("type", {}).get("value", "-"),
        "bmi": first.get("bmi", {}).get("value", "-"),
        "sbp": first.get("sbp", {}).get("value", "-"),
        "dbp": first.get("dbp", {}).get("value", "-"),
        "chol": first.get("chol", {}).get("value", "-"),
        "ldl": first.get("ldl", {}).get("value", "-"),
    }
    exercises = set([r["recName"]["value"] for r in bindings if "recName" in r])
    warnings = set([r["warnDesc"]["value"] for r in bindings if "warnDesc" in r])
    return {"info": info, "exercises": list(exercises), "warnings": list(warnings)}

def save_raw_patient_data(data):
    pid = f"Patient{data['id']}"
    delete_patient(data['id'])
    def get_val(key): return data.get(key) if data.get(key) else "0"
    triples = f"""
        ex:{pid} a ex:Patient ; ex:diabetType ex:{data['type']} ; ex:firstname "{data.get('firstname', '-')}" ; ex:lastname "{data.get('lastname', '-')}" ; ex:hasPhysicalExam ex:{pid}_PE ; ex:hasLabExam ex:{pid}_LE .
        ex:{pid}_PE a ex:PhysicalExam ; ex:hasBMI "{get_val('bmi')}"^^xsd:decimal ; ex:hasSBP "{get_val('sbp')}"^^xsd:decimal ; ex:hasDBP "{get_val('dbp')}"^^xsd:decimal .
        ex:{pid}_LE a ex:LabExam ; ex:hasTotalCholesterol "{get_val('chol')}"^^xsd:decimal ; ex:hasLDL "{get_val('ldl')}"^^xsd:decimal ; ex:hasHDL "{get_val('hdl')}"^^xsd:decimal ; ex:hasTriglyceride "{get_val('tri')}"^^xsd:decimal .
    """
    sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> INSERT DATA {{ {triples} }}"); sparql_write.query()

def delete_patient(patient_id):
    pid = f"Patient{patient_id}"
    sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ?s ?p ?o . ?pe ?pp ?oo . ?le ?lp ?lo }} WHERE {{ ?s ?p ?o . FILTER(?s = ex:{pid}) OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} }}"); sparql_write.query()