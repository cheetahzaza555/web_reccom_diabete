import io
import requests
import traceback
import sys
import uuid
import re
import time
sys.stdout.reconfigure(encoding='utf-8')
from SPARQLWrapper import SPARQLWrapper, JSON, POST
from owlready2 import *

# ==========================================
# 1. Config
# ==========================================
REPO_NAME = "Project" 
GRAPHDB_BASE = "http://localhost:7200/repositories"
GRAPHDB_READ = f"{GRAPHDB_BASE}/{REPO_NAME}"
GRAPHDB_WRITE = f"{GRAPHDB_BASE}/{REPO_NAME}/statements"

sparql_read = SPARQLWrapper(GRAPHDB_READ)
sparql_read.setReturnFormat(JSON)
sparql_write = SPARQLWrapper(GRAPHDB_WRITE)
sparql_write.setMethod(POST)

# ==========================================
# 2. Helpers
# ==========================================
def validate_id(val):
    if not val: return False
    return bool(re.match(r'^[A-Za-z0-9_-]{1,64}$', str(val)))

def escape_sparql(text):
    if not text: return ""
    return str(text).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')

def safe_float(value):
    try:
        if value is None or str(value).strip() == "": return None
        return float(value)
    except (ValueError, TypeError):
        return None

def get_thai_text(entity):
    if hasattr(entity, "description") and entity.description: return str(entity.description[0])
    if hasattr(entity, "label") and entity.label: return str(entity.label[0])
    return entity.name

def safe_get_name(uri):
    if not uri: return ""
    return re.split(r'[#/]', uri)[-1]

# ==========================================
# 3. Load Ontology
# ==========================================
def load_ontology_from_graphdb():
    print(f"🌍 Loading Ontology from {REPO_NAME}...")
    headers = {"Accept": "text/plain"} 
    params = {"infer": "false"} 
    try:
        response = requests.get(f"{GRAPHDB_READ}/statements", headers=headers, params=params)
        response.raise_for_status()
        raw_data = response.content.decode('utf-8')
        clean_lines = [line for line in raw_data.splitlines() if "http://www.w3.org/2002/07/owl#imports" not in line]
        clean_data = "\n".join(clean_lines)
        onto = get_ontology("http://example.org/diabetes_from_db").load(fileobj=io.BytesIO(clean_data.encode('utf-8')), format="ntriples")
        print(f"✅ Loaded! Rules count: {len(list(onto.rules()))}")
        
        return onto
    except Exception as e:
        print(f"❌ Error loading ontology: {e}")
        return None

onto = load_ontology_from_graphdb()

if onto:
    ex = onto.get_namespace("http://example.org/diabetes#")
    with onto:
        class Patient(Thing): namespace = ex
        class PhysicalExam(Thing): namespace = ex
        class LabExam(Thing): namespace = ex
        class Exercise(Thing): namespace = ex
        class DiabetType(Thing): namespace = ex
        class PatientWarning(Thing): namespace = ex
        class Comorbidity(Thing): namespace = ex 
        class Complication(Thing): namespace = ex 
        
        class hasBMI(DataProperty): namespace = ex; range = [float]
        class hasSBP(DataProperty): namespace = ex; range = [float]
        class hasDBP(DataProperty): namespace = ex; range = [float]
        class hasTotalCholesterol(DataProperty): namespace = ex; range = [float]
        class hasLDL(DataProperty): namespace = ex; range = [float]
        class hasHDL(DataProperty): namespace = ex; range = [float]
        class hasTriglyceride(DataProperty): namespace = ex; range = [float]
        class hasFPG(DataProperty): namespace = ex; range = [float]
        class hasWeight(DataProperty): namespace = ex; range = [float]
        class hasHeight(DataProperty): namespace = ex; range = [float]
        
        class hasKetone(DataProperty): namespace = ex; range = [str]
        class hasMicroalbuminurin(DataProperty): namespace = ex; range = [str]
        
        class diabetType(ObjectProperty): namespace = ex; range = [DiabetType]
        class hasPhysicalExam(ObjectProperty): namespace = ex; range = [PhysicalExam]
        class hasLabExam(ObjectProperty): namespace = ex; range = [LabExam]
        class recommendedExercise(ObjectProperty): namespace = ex; range = [Exercise]
        class hasPatientWarning(ObjectProperty): namespace = ex; range = [PatientWarning]
        class hasComorbidity(ObjectProperty): namespace = ex; range = [Comorbidity]
        class hasComplication(ObjectProperty): namespace = ex; range = [Complication]
        class hasSpecialComplication(ObjectProperty): namespace = ex; range = [Complication]

# ==========================================
# 4. Core Logic (Updated for Multiple Specials)
# ==========================================
def process_patient_realtime(patient_id, input_data=None):
    if not validate_id(patient_id): return [], [], [], []
    if not onto: return [], [], [], [] 

    unique_suffix = uuid.uuid4().hex[:8]
    pid_mem = f"Patient_Mem_{patient_id}_{unique_suffix}"
    p, pe, le = None, None, None

    try:
        # 1. เตรียมข้อมูล
        data = {}
        target_specials = [] 

        if input_data:
            print(f"⚡ Processing {patient_id} using Direct Input...")
            # ... (Logic จัดการ Special Complication เหมือนเดิม) ...
            raw_special = input_data.get('special')
            if isinstance(raw_special, list):
                if not raw_special: target_specials.append("NoOtherComplication")
                else: target_specials.extend(raw_special)
            elif isinstance(raw_special, str):
                if raw_special and raw_special != "None": target_specials.append(raw_special)
                else: target_specials.append("NoOtherComplication")

            data = {
                'type': input_data.get('type', 'T2DM'),
                'weight': safe_float(input_data.get('weight')), # ✅ รับน้ำหนัก
                'height': safe_float(input_data.get('height')), # ✅ รับส่วนสูง
                'bmi': safe_float(input_data.get('bmi')), 
                'sbp': safe_float(input_data.get('sbp')),
                'dbp': safe_float(input_data.get('dbp')), 
                'chol': safe_float(input_data.get('chol')),
                'ldl': safe_float(input_data.get('ldl')),
                'hdl': safe_float(input_data.get('hdl')),
                'tri': safe_float(input_data.get('tri')),
                'fpg': safe_float(input_data.get('fpg')),
                'ketone': input_data.get('ketone') or "Negative",
                'micro': input_data.get('micro') or "Negative",
            }
        else:
            # กรณีดึงจาก DB
            print(f"📥 Fetching {patient_id} from DB...")
            # ✅ เพิ่ม ?weight ?height ใน Query
            query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            SELECT ?typeUri ?weight ?height ?bmi ?sbp ?dbp ?chol ?ldl ?hdl ?tri ?fpg ?ketone ?micro ?specialUri
            WHERE {{
                ex:Patient{patient_id} a ex:Patient ; ex:diabetType ?typeUri .
                OPTIONAL {{ ex:Patient{patient_id} ex:hasPhysicalExam ?pe . 
                            OPTIONAL {{ ?pe ex:hasWeight ?weight }}   # ✅
                            OPTIONAL {{ ?pe ex:hasHeight ?height }}   # ✅
                            OPTIONAL {{ ?pe ex:hasBMI ?bmi }} 
                            OPTIONAL {{ ?pe ex:hasSBP ?sbp }} 
                            OPTIONAL {{ ?pe ex:hasDBP ?dbp }}
                            OPTIONAL {{ ?pe ex:hasSpecialComplication ?specialUri }} }}
                OPTIONAL {{ ex:Patient{patient_id} ex:hasLabExam ?le . 
                            OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} 
                            OPTIONAL {{ ?le ex:hasHDL ?hdl }} OPTIONAL {{ ?le ex:hasTriglyceride ?tri }}
                            OPTIONAL {{ ?le ex:hasFPG ?fpg }} OPTIONAL {{ ?le ex:hasKetone ?ketone }} OPTIONAL {{ ?le ex:hasMicroalbuminurin ?micro }} }}
            }}
            """
            sparql_read.setQuery(query)
            results = sparql_read.query().convert()
            if not results["results"]["bindings"]:
                return [], [], [], []

            for r in results["results"]["bindings"]:
                s_uri = r.get('specialUri', {}).get('value')
                if s_uri:
                    s_name = safe_get_name(s_uri)
                    if s_name not in target_specials:
                        target_specials.append(s_name)
            
            if not target_specials: target_specials.append("NoOtherComplication")

            row = results["results"]["bindings"][0]
            db_type = safe_get_name(row.get('typeUri', {}).get('value')) or 'T2DM'
            
            data = {
                'type': db_type,
                'weight': safe_float(row.get('weight', {}).get('value')), # ✅
                'height': safe_float(row.get('height', {}).get('value')), # ✅
                'bmi': safe_float(row.get('bmi', {}).get('value')), 
                'sbp': safe_float(row.get('sbp', {}).get('value')),
                'dbp': safe_float(row.get('dbp', {}).get('value')), 
                'chol': safe_float(row.get('chol', {}).get('value')),
                'ldl': safe_float(row.get('ldl', {}).get('value')),
                'hdl': safe_float(row.get('hdl', {}).get('value')),
                'tri': safe_float(row.get('tri', {}).get('value')),
                'fpg': safe_float(row.get('fpg', {}).get('value')),
                'ketone': row.get('ketone', {}).get('value') or "Negative",
                'micro': row.get('micro', {}).get('value') or "Negative",
            }

        # ✅ Auto-Calculate BMI (ถ้าไม่มี BMI แต่มี นน/สส)
        if data['bmi'] is None and data['weight'] and data['height']:
            try:
                h_m = data['height'] / 100.0
                data['bmi'] = round(data['weight'] / (h_m * h_m), 2)
                print(f"🧮 Auto-calculated BMI: {data['bmi']}")
            except: pass

        if data['fpg'] is None: data['fpg'] = 100.0

        print(f"🧐 Analyzed Data: {data}")

        with onto:
            p = ex.Patient(pid_mem)
            
            target_type = data['type']
            type_obj = getattr(ex, target_type, None)
            if not type_obj: type_obj = onto.search_one(iri=f"*{target_type}") 
            if not type_obj: type_obj = ex.DiabetType(target_type)
            p.diabetType = [type_obj]
                
            pe = ex.PhysicalExam(f"PE_{unique_suffix}")
            # ✅ ใส่ค่าลง Instance
            if data['weight'] is not None: pe.hasWeight = [data['weight']]
            if data['height'] is not None: pe.hasHeight = [data['height']]
            if data['bmi'] is not None: pe.hasBMI = [data['bmi']]
            if data['sbp'] is not None: pe.hasSBP = [data['sbp']]
            if data['dbp'] is not None: pe.hasDBP = [data['dbp']]
            
            pe.hasSpecialComplication = [] 
            for sp_name in target_specials:
                sp_obj = getattr(ex, sp_name, None)
                if not sp_obj: sp_obj = onto.search_one(iri=f"*{sp_name}")
                if not sp_obj: sp_obj = ex.Complication(sp_name)
                pe.hasSpecialComplication.append(sp_obj)
            
            p.hasPhysicalExam = [pe]
            
            le = ex.LabExam(f"LE_{unique_suffix}")
            if data['chol'] is not None: le.hasTotalCholesterol = [data['chol']]
            if data['ldl'] is not None: le.hasLDL = [data['ldl']]
            if data['hdl'] is not None: le.hasHDL = [data['hdl']]
            if data['tri'] is not None: le.hasTriglyceride = [data['tri']]
            if data['fpg'] is not None: le.hasFPG = [data['fpg']]
            le.hasKetone = [data['ketone']]
            le.hasMicroalbuminurin = [data['micro']]
            p.hasLabExam = [le]

        print("🧠 Running Reasoner...")
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        
        # ... (ส่วน Extract Result เหมือนเดิม) ...
        print("🔍 Extracting Results...")
        recs, warns, comorbs, complis = [], [], [], [] 
        s_recs, s_warns, s_comorbs, s_complis = [], [], [], []

        for prop in p.get_properties():
            values = prop[p]
            prop_iri = prop.iri
            target_list, save_list = None, None
            
            if prop_iri.endswith("recommendedExercise"): target_list, save_list = recs, s_recs
            elif prop_iri.endswith("hasPatientWarning"): target_list, save_list = warns, s_warns
            elif prop_iri.endswith("hasComorbidity"): target_list, save_list = comorbs, s_comorbs
            elif prop_iri.endswith("hasComplication"): target_list, save_list = complis, s_complis
            
            if target_list is not None:
                for val in values:
                    if hasattr(val, 'name'):
                        target_list.append(get_thai_text(val))
                        save_list.append(val.name)

        recs = list(set(recs)); warns = list(set(warns)); comorbs = list(set(comorbs)); complis = list(set(complis))
        s_recs = list(set(s_recs)); s_warns = list(set(s_warns)); s_comorbs = list(set(s_comorbs)); s_complis = list(set(s_complis))

        print(f"✅ Result: W={len(warns)}, Cb={len(comorbs)}, Cp={len(complis)}")
        
        save_results_to_db(patient_id, s_recs, s_warns, s_comorbs, s_complis)
        return recs, warns, comorbs, complis

    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return [], [], [], [f"Error: {str(e)}"]
    
    finally:
        if p: destroy_entity(p)
        if pe: destroy_entity(pe)
        if le: destroy_entity(le)

def save_results_to_db(pid_num, recs, warns, comorbs, complis):
    if not validate_id(pid_num): return
    pid = f"Patient{pid_num}"
    
    del_q = f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ex:{pid} ex:hasPatientWarning ?w . ex:{pid} ex:recommendedExercise ?r . ex:{pid} ex:hasComorbidity ?c . ex:{pid} ex:hasComplication ?cp }} WHERE {{ OPTIONAL {{ ex:{pid} ex:hasPatientWarning ?w }} OPTIONAL {{ ex:{pid} ex:recommendedExercise ?r }} OPTIONAL {{ ex:{pid} ex:hasComorbidity ?c }} OPTIONAL {{ ex:{pid} ex:hasComplication ?cp }} }}"
    sparql_write.setQuery(del_q); sparql_write.query()
    
    triples = []
    for x in recs: triples.append(f"ex:{pid} ex:recommendedExercise ex:{x} .")
    for x in warns: triples.append(f"ex:{pid} ex:hasPatientWarning ex:{x} .")
    for x in comorbs: triples.append(f"ex:{pid} ex:hasComorbidity ex:{x} .")
    for x in complis: triples.append(f"ex:{pid} ex:hasComplication ex:{x} .")
    
    if triples:
        ins_q = f"PREFIX ex: <http://example.org/diabetes#> INSERT DATA {{ {' '.join(triples)} }}"
        sparql_write.setQuery(ins_q); sparql_write.query()
        print(f"💾 Saved {len(triples)} results")

def save_raw_patient_data(data):
    if not validate_id(data.get('id')): return
    pid = f"Patient{data['id']}"
    
    try:
        # 1. ลบข้อมูลเก่า
        sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ?s ?p ?o . ?pe ?pp ?oo . ?le ?lp ?lo }} WHERE {{ ?s ?p ?o . FILTER(?s = ex:{pid}) OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} }}")
        sparql_write.query()
        
        # 2. เตรียมข้อมูล
        fname = escape_sparql(data.get('firstname', '-'))
        lname = escape_sparql(data.get('lastname', '-'))
        ketone_val = escape_sparql(data.get('ketone') or "Negative")
        micro_val = escape_sparql(data.get('micro') or "Negative")
        
        def val(k): return safe_float(data.get(k)) or 0

        # จัดการ Special Complication... (เหมือนเดิม)
        raw_special = data.get('special')
        special_triples = ""
        if isinstance(raw_special, list):
            if not raw_special: special_triples = f"ex:{pid}_PE ex:hasSpecialComplication ex:NoOtherComplication ."
            else:
                for sp in raw_special:
                    special_triples += f"ex:{pid}_PE ex:hasSpecialComplication ex:{escape_sparql(sp)} .\n"
        elif isinstance(raw_special, str) and raw_special != "None":
            special_triples = f"ex:{pid}_PE ex:hasSpecialComplication ex:{escape_sparql(raw_special)} ."
        else:
            special_triples = f"ex:{pid}_PE ex:hasSpecialComplication ex:NoOtherComplication ."

        # 3. สร้าง Triples (✅ เพิ่ม ex:hasWeight และ ex:hasHeight)
        triples = f"""
            ex:{pid} a ex:Patient ; ex:diabetType ex:{escape_sparql(data['type'])} ; 
                     ex:firstname "{fname}" ; ex:lastname "{lname}" ; 
                     ex:hasPhysicalExam ex:{pid}_PE ; ex:hasLabExam ex:{pid}_LE .
            
            ex:{pid}_PE a ex:PhysicalExam ; 
                        ex:hasWeight "{val('weight')}"^^xsd:decimal ; 
                        ex:hasHeight "{val('height')}"^^xsd:decimal ; 
                        ex:hasBMI "{val('bmi')}"^^xsd:decimal ; 
                        ex:hasSBP "{val('sbp')}"^^xsd:decimal ; ex:hasDBP "{val('dbp')}"^^xsd:decimal .
            
            {special_triples} 
            
            ex:{pid}_LE a ex:LabExam ; ex:hasTotalCholesterol "{val('chol')}"^^xsd:decimal ; 
                        ex:hasLDL "{val('ldl')}"^^xsd:decimal ; ex:hasHDL "{val('hdl')}"^^xsd:decimal ; 
                        ex:hasTriglyceride "{val('tri')}"^^xsd:decimal ;
                        ex:hasFPG "{val('fpg')}"^^xsd:decimal ; 
                        ex:hasKetone "{ketone_val}" ; ex:hasMicroalbuminurin "{micro_val}" . 
        """
        
        sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> INSERT DATA {{ {triples} }}")
        sparql_write.query()
        
    except Exception as e:
        print(f"❌ Error saving raw data: {e}")

def delete_patient(patient_id):
    # (ใช้ Logic เดิม)
    if not validate_id(patient_id): return
    pid = f"Patient{patient_id}"
    sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ?s ?p ?o . ?pe ?pp ?oo . ?le ?lp ?lo }} WHERE {{ ?s ?p ?o . FILTER(?s = ex:{pid}) OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} }}")
    sparql_write.query()

def get_patient_profile(patient_id):
    if not validate_id(patient_id): return None
    pid = f"Patient{patient_id}"
    # ✅ เพิ่ม ?weight ?height ใน SELECT และ OPTIONAL
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?fname ?lname ?type ?weight ?height ?bmi ?sbp ?dbp ?chol ?ldl ?fpg ?ketone ?micro ?specialName ?recName ?warnDesc ?comorbName ?compliName
    WHERE {{
        ex:{pid} a ex:Patient ; ex:diabetType ?typeUri .
        BIND(STRAFTER(STR(?typeUri), "#") AS ?type)
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }} OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
        OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . 
                    OPTIONAL {{ ?pe ex:hasWeight ?weight }} 
                    OPTIONAL {{ ?pe ex:hasHeight ?height }}
                    OPTIONAL {{ ?pe ex:hasBMI ?bmi }} OPTIONAL {{ ?pe ex:hasSBP ?sbp }} OPTIONAL {{ ?pe ex:hasDBP ?dbp }} 
                    OPTIONAL {{ ?pe ex:hasSpecialComplication ?special . BIND(STRAFTER(STR(?special), "#") AS ?specialName) }} }}
        OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . 
                    OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} 
                    OPTIONAL {{ ?le ex:hasFPG ?fpg }} OPTIONAL {{ ?le ex:hasKetone ?ketone }} OPTIONAL {{ ?le ex:hasMicroalbuminurin ?micro }} }}
        OPTIONAL {{ ex:{pid} ex:recommendedExercise ?rec . OPTIONAL {{ ?rec rdfs:label ?recLabel }} BIND(COALESCE(?recLabel, STRAFTER(STR(?rec), "#")) AS ?recName) }} 
        OPTIONAL {{ ex:{pid} ex:hasPatientWarning ?warn . OPTIONAL {{ ?warn ex:description ?wDesc }} OPTIONAL {{ ?warn rdfs:label ?wLabel }} BIND(COALESCE(?wDesc, ?wLabel, STRAFTER(STR(?warn), "#")) AS ?warnDesc) }}
        OPTIONAL {{ ex:{pid} ex:hasComorbidity ?comorb . OPTIONAL {{ ?comorb rdfs:label ?cLabel }} BIND(COALESCE(?cLabel, STRAFTER(STR(?comorb), "#")) AS ?comorbName) }}
        OPTIONAL {{ ex:{pid} ex:hasComplication ?compli . OPTIONAL {{ ?compli rdfs:label ?cpLabel }} BIND(COALESCE(?cpLabel, STRAFTER(STR(?compli), "#")) AS ?compliName) }}
    }}
    """
    sparql_read.setQuery(query)
    results = sparql_read.query().convert()
    bindings = results["results"]["bindings"]
    if not bindings: return None
    first = bindings[0]
    info = {
        "firstname": first.get("fname", {}).get("value", "-"), "lastname": first.get("lname", {}).get("value", "-"),
        "type": first.get("type", {}).get("value", "-"), 
        "weight": first.get("weight", {}).get("value", "-"), # ✅
        "height": first.get("height", {}).get("value", "-"), # ✅
        "bmi": first.get("bmi", {}).get("value", "-"),
        "sbp": first.get("sbp", {}).get("value", "-"), "dbp": first.get("dbp", {}).get("value", "-"),
        "chol": first.get("chol", {}).get("value", "-"), "ldl": first.get("ldl", {}).get("value", "-"),
        "fpg": first.get("fpg", {}).get("value", "-"), "ketone": first.get("ketone", {}).get("value", "-"),
        "micro": first.get("micro", {}).get("value", "-"), "special": first.get("specialName", {}).get("value", ""),
    }
    def extract_set(key): return set([r[key]["value"] for r in bindings if key in r])
    return {
        "info": info, "exercises": list(extract_set("recName")), "warnings": list(extract_set("warnDesc")),
        "comorbs": list(extract_set("comorbName")), "complis": list(extract_set("compliName"))
    }
