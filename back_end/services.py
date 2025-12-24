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
        
        class intensityOfExercise(ObjectProperty): namespace = ex
        class exerciseFrequency(ObjectProperty): namespace = ex

# ==========================================
# 4. Core Logic (Fixed & Debugged)
# ==========================================
def process_patient_realtime(patient_id, input_data=None):
    if not validate_id(patient_id) or not onto: return [], [], [], []

    unique_suffix = uuid.uuid4().hex[:8]
    pid_mem = f"Patient_Mem_{patient_id}_{unique_suffix}"
    p = None

    try:
        # 1. เตรียมตัวแปร
        data = {}
        target_specials = []
        target_favorites = []  # ✅ ประกาศไว้ก่อนเลยกันพลาด

        if input_data:
            print(f"⚡ Processing {patient_id} (Direct)...")
            data = input_data
            raw_sp = input_data.get('special')
            if isinstance(raw_sp, list): target_specials = raw_sp
            elif isinstance(raw_sp, str) and raw_sp != "None": target_specials = [raw_sp]
            
            # รับค่า favorites จาก Input
            target_favorites = input_data.get('favorites', [])
        
        else:
            print(f"📥 Fetching {patient_id} from DB...")
            query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            SELECT ?typeUri ?weight ?height ?bmi ?sbp ?dbp ?chol ?ldl ?hdl ?tri ?fpg ?ketone ?micro ?specialUri ?favName
            WHERE {{
                ex:Patient{patient_id} a ex:Patient ; ex:diabetType ?typeUri .
                OPTIONAL {{ ex:Patient{patient_id} ex:hasPhysicalExam ?pe . 
                            OPTIONAL {{ ?pe ex:hasWeight ?weight }} OPTIONAL {{ ?pe ex:hasHeight ?height }} 
                            OPTIONAL {{ ?pe ex:hasBMI ?bmi }} OPTIONAL {{ ?pe ex:hasSBP ?sbp }} OPTIONAL {{ ?pe ex:hasDBP ?dbp }}
                            OPTIONAL {{ ?pe ex:hasSpecialComplication ?specialUri }} }}
                OPTIONAL {{ ex:Patient{patient_id} ex:hasLabExam ?le . 
                            OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} 
                            OPTIONAL {{ ?le ex:hasHDL ?hdl }} OPTIONAL {{ ?le ex:hasTriglyceride ?tri }}
                            OPTIONAL {{ ?le ex:hasFPG ?fpg }} OPTIONAL {{ ?le ex:hasKetone ?ketone }} OPTIONAL {{ ?le ex:hasMicroalbuminurin ?micro }} }}
                OPTIONAL {{ ex:Patient{patient_id} ex:favoriteExercise ?fav . BIND(STRAFTER(STR(?fav), "#") AS ?favName) }}
            }}
            """
            sparql_read.setQuery(query)
            results = sparql_read.query().convert()
            if not results["results"]["bindings"]: return [], [], [], []

            for r in results["results"]["bindings"]:
                s_uri = r.get('specialUri', {}).get('value')
                if s_uri:
                    s_name = safe_get_name(s_uri)
                    if s_name not in target_specials: target_specials.append(s_name)
                
                # ✅ ดึง Favorites จาก DB
                f_name = r.get('favName', {}).get('value')
                if f_name and f_name not in target_favorites: target_favorites.append(f_name)
            
            if not target_specials: target_specials.append("NoOtherComplication")
            row = results["results"]["bindings"][0]
            
            data = {
                'type': safe_get_name(row.get('typeUri', {}).get('value')) or 'T2DM',
                'weight': safe_float(row.get('weight', {}).get('value')),
                'height': safe_float(row.get('height', {}).get('value')),
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

        if data['bmi'] is None and data['weight'] and data['height']:
            try: data['bmi'] = round(data['weight'] / ((data['height']/100)**2), 2)
            except: pass
        if data['fpg'] is None: data['fpg'] = 100.0

        print(f"🧐 Analyzed: {data}")
        print(f"⭐ Favorites: {target_favorites}")

        with onto:
            p = ex.Patient(pid_mem)
            t_obj = onto.search_one(iri=f"*{data['type']}") or ex.DiabetType(data['type'])
            p.diabetType = [t_obj]
                
            pe = ex.PhysicalExam(f"PE_{unique_suffix}")
            if data['weight']: pe.hasWeight = [data['weight']]
            if data['height']: pe.hasHeight = [data['height']]
            if data['bmi']: pe.hasBMI = [data['bmi']]
            if data['sbp']: pe.hasSBP = [data['sbp']]
            if data['dbp']: pe.hasDBP = [data['dbp']]
            
            pe.hasSpecialComplication = [] 
            for sp in target_specials:
                sp_obj = onto.search_one(iri=f"*{sp}") or ex.Complication(sp)
                pe.hasSpecialComplication.append(sp_obj)
            p.hasPhysicalExam = [pe]
            
            le = ex.LabExam(f"LE_{unique_suffix}")
            if data['chol']: le.hasTotalCholesterol = [data['chol']]
            if data['ldl']: le.hasLDL = [data['ldl']]
            if data['hdl']: le.hasHDL = [data['hdl']]
            if data['tri']: le.hasTriglyceride = [data['tri']]
            if data['fpg']: le.hasFPG = [data['fpg']]
            le.hasKetone = [data['ketone']]
            le.hasMicroalbuminurin = [data['micro']]
            p.hasLabExam = [le]

            p.favoriteExercise = []
            for f in target_favorites:
                # ✅ ค้นหาท่าออกกำลังกายให้เจอจริงๆ
                f_obj = onto.search_one(iri=f"*{f}")
                if not f_obj: 
                    print(f"⚠️ Warning: Exercise '{f}' not found in Ontology! Creating temp instance.")
                    f_obj = ex.Exercise(f)
                p.favoriteExercise.append(f_obj)

        print("🧠 Running Reasoner...")
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        
        # --- 🕵️‍♂️ DEBUG SECTION (ใส่ตรงนี้ไม่พังแน่นอน) ---
        print("\n🕵️‍♂️ --- DEBUGGING EXERCISE ---")
        print(f"User Favorites: {target_favorites}")
        
        # 1. เช็ค Avoid List
        avoids = [val.name for val in getattr(p, "avoidExercise", [])]
        print(f"⛔ Avoid List: {avoids}")
        
        # 2. เช็ค Recommended List
        recs_debug = [val.name for val in getattr(p, "recommendedExercise", [])]
        print(f"✅ Recommended (Rule-based): {recs_debug}")
        
        # 3. เช็ค Fallback Logic
        fallback_candidates = []
        if not recs_debug and target_favorites:
            for f_obj in p.favoriteExercise:
                if f_obj.name not in avoids:
                    fallback_candidates.append(f_obj.name)
        print(f"🔄 Fallback Candidates: {fallback_candidates}")
        print("--------------------------------\n")
        # ------------------------------------------

        print("🔍 Extracting Results...")
        recs, warns, comorbs, complis = [], [], [], [] 
        s_recs, s_warns, s_comorbs, s_complis = [], [], [], []

        # 1. Exercises (Logic ที่รวม Debug แล้ว)
        recs_list = list(p.recommendedExercise)
        
        # Fallback
        if not recs_list and target_favorites:
            avoid = [val.name for val in getattr(p, "avoidExercise", [])]
            for f in p.favoriteExercise:
                if f.name not in avoid: recs_list.append(f)

        for r in list(set(recs_list)):
            s_recs.append(r.name)
            name = get_thai_text(r)
            
            # ดึง Detail แบบปลอดภัย
            details = []
            try:
                # Intensity
                ints = getattr(r, "intensityOfExercise", [])
                if not isinstance(ints, list): ints = [ints]
                for i in ints:
                    if hasattr(i, 'label') and i.label: details.append(str(i.label[0]))
                    elif hasattr(i, 'name'): details.append(str(i.name))
                    else: details.append(str(i))
                
                # Frequency
                freqs = getattr(r, "exerciseFrequency", [])
                if not isinstance(freqs, list): freqs = [freqs]
                for f in freqs:
                    if hasattr(f, 'label') and f.label: details.append(str(f.label[0]))
                    elif hasattr(f, 'name'): details.append(str(f.name))
                    else: details.append(str(f))
            except: pass
            
            if details: recs.append(f"{name} ({', '.join(details)})")
            else: recs.append(name)

        # 2. Warnings / Others
        for w in p.hasPatientWarning: 
            warns.append(get_thai_text(w)); s_warns.append(w.name)
        for c in p.hasComorbidity: 
            comorbs.append(get_thai_text(c)); s_comorbs.append(c.name)
        for cp in p.hasComplication: 
            complis.append(get_thai_text(cp)); s_complis.append(cp.name)

        recs = list(set(recs)); warns = list(set(warns))
        comorbs = list(set(comorbs)); complis = list(set(complis))

        print(f"✅ Result: Ex={len(recs)}, W={len(warns)}")
        
        save_results_to_db(patient_id, list(set(s_recs)), list(set(s_warns)), list(set(s_comorbs)), list(set(s_complis)))
        return recs, warns, comorbs, complis

    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return [], [], [], [f"Error: {str(e)}"]
    finally:
        if p: destroy_entity(p)
        
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
    
    # 🔥 [แก้ Query] เพิ่มการดึง Intensity และ Frequency
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?fname ?lname ?type ?weight ?height ?bmi ?sbp ?dbp ?chol ?ldl ?fpg ?ketone ?micro ?specialName 
           ?recName ?recInten ?recFreq 
           ?warnDesc ?comorbName ?compliName
    WHERE {{
        ex:{pid} a ex:Patient ; ex:diabetType ?typeUri .
        BIND(STRAFTER(STR(?typeUri), "#") AS ?type)
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }} OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
        OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . 
                    OPTIONAL {{ ?pe ex:hasWeight ?weight }} OPTIONAL {{ ?pe ex:hasHeight ?height }}
                    OPTIONAL {{ ?pe ex:hasBMI ?bmi }} OPTIONAL {{ ?pe ex:hasSBP ?sbp }} OPTIONAL {{ ?pe ex:hasDBP ?dbp }} 
                    OPTIONAL {{ ?pe ex:hasSpecialComplication ?special . BIND(STRAFTER(STR(?special), "#") AS ?specialName) }} }}
        OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . 
                    OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} 
                    OPTIONAL {{ ?le ex:hasFPG ?fpg }} OPTIONAL {{ ?le ex:hasKetone ?ketone }} OPTIONAL {{ ?le ex:hasMicroalbuminurin ?micro }} }}
        
        # 🔥 [แก้ตรงนี้] ดึง Exercise Details แบบปลอดภัย
        OPTIONAL {{ 
            ex:{pid} ex:recommendedExercise ?rec . 
            OPTIONAL {{ ?rec rdfs:label ?recLabel }} 
            BIND(COALESCE(?recLabel, STRAFTER(STR(?rec), "#")) AS ?recName)
            
            # ดึง Intensity: ถ้ามี Label เอา Label, ถ้าไม่มีเอาค่าตรงๆ (String), ถ้าเป็น URI เอาชื่อหลัง #
            OPTIONAL {{ 
                ?rec ex:intensityOfExercise ?intRaw . 
                OPTIONAL {{ ?intRaw rdfs:label ?intLabel }}
                BIND(COALESCE(?intLabel, STRAFTER(STR(?intRaw), "#"), STR(?intRaw)) AS ?recInten)
            }}
            
            # ดึง Frequency: ทำเหมือนกัน
            OPTIONAL {{ 
                ?rec ex:exerciseFrequency ?frqRaw . 
                OPTIONAL {{ ?frqRaw rdfs:label ?frqLabel }}
                BIND(COALESCE(?frqLabel, STRAFTER(STR(?frqRaw), "#"), STR(?frqRaw)) AS ?recFreq)
            }}
        }} 
        
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
        "weight": first.get("weight", {}).get("value", "-"),
        "height": first.get("height", {}).get("value", "-"),
        "bmi": first.get("bmi", {}).get("value", "-"),
        "sbp": first.get("sbp", {}).get("value", "-"), "dbp": first.get("dbp", {}).get("value", "-"),
        "chol": first.get("chol", {}).get("value", "-"), "ldl": first.get("ldl", {}).get("value", "-"),
        "fpg": first.get("fpg", {}).get("value", "-"), "ketone": first.get("ketone", {}).get("value", "-"),
        "micro": first.get("micro", {}).get("value", "-"), "special": first.get("specialName", {}).get("value", ""),
    }

    # 🔥 [Logic รวมข้อมูล] Group ชื่อท่า + รายละเอียด ไม่ให้บรรทัดซ้ำ
    ex_dict = {}
    for r in bindings:
        if "recName" in r:
            name = r["recName"]["value"]
            if name not in ex_dict: ex_dict[name] = {"int": set(), "freq": set()}
            
            if "recInten" in r: ex_dict[name]["int"].add(r["recInten"]["value"])
            if "recFreq" in r: ex_dict[name]["freq"].add(r["recFreq"]["value"])
            
    final_exercises = []
    for name, det in ex_dict.items():
        info_parts = []
        if det["int"]: info_parts.append(f"ความหนัก: {', '.join(det['int'])}")
        if det["freq"]: info_parts.append(f"ความถี่: {', '.join(det['freq'])}")
        
        if info_parts:
            final_exercises.append(f"{name} ({' | '.join(info_parts)})")
        else:
            final_exercises.append(name)

    def extract_set(key): return list(set([r[key]["value"] for r in bindings if key in r]))

    return {
        "info": info, 
        "exercises": final_exercises, # ✅ ส่งค่าที่จัด Format แล้วกลับไป
        "warnings": extract_set("warnDesc"),
        "comorbs": extract_set("comorbName"), 
        "complis": extract_set("compliName")
    }