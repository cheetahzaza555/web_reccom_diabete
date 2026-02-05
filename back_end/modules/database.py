# modules/database.py
import re
from SPARQLWrapper import SPARQLWrapper, JSON, POST
from modules.config import GRAPHDB_READ, GRAPHDB_WRITE

# Setup Connection
sparql_read = SPARQLWrapper(GRAPHDB_READ)
sparql_read.setReturnFormat(JSON)
sparql_write = SPARQLWrapper(GRAPHDB_WRITE)
sparql_write.setMethod(POST)

# --- Helpers ---
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

# --- Database Functions ---

def save_raw_patient_data(data):
    if not validate_id(data.get('id')): return

    raw_id = str(data.get('id')).replace("Patient", "")  
    pid = f"Patient{raw_id}"                             
    
    pe_node = f"ex:PE1P00{raw_id}"   
    le_node = f"ex:Lab1P00{raw_id}"   

    try:
        # 1. ลบข้อมูลเก่า
        sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ?s ?p ?o . ?pe ?pp ?oo . ?le ?lp ?lo }} WHERE {{ ?s ?p ?o . FILTER(?s = ex:{pid}) OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} }}")
        sparql_write.query()
        
        # 2. เตรียมข้อมูล
        fname = escape_sparql(data.get('firstname', '-'))
        lname = escape_sparql(data.get('lastname', '-'))
        
        # 🔥 [เพิ่ม] ดึงค่าเพศ
        gender_val = escape_sparql(data.get('gender', '-')) 

        insulin_val = escape_sparql(data.get('insulin_use') or "false")
        ketone_val = escape_sparql(data.get('ketone') or "Negative")
        micro_val = escape_sparql(data.get('micro') or "Negative")
        
        def val(k): return safe_float(data.get(k)) or 0

        # จัดการ Special Complication
        raw_special = data.get('special')
        special_triples = ""
        if isinstance(raw_special, list):
            if not raw_special: special_triples = f"{pe_node} ex:hasSpecialComplication ex:NoOtherComplication ."
            else:
                for sp in raw_special:
                    special_triples += f"{pe_node} ex:hasSpecialComplication ex:{escape_sparql(sp)} .\n"
        elif isinstance(raw_special, str) and raw_special != "None":
            special_triples = f"{pe_node} ex:hasSpecialComplication ex:{escape_sparql(raw_special)} ."
        else:
            special_triples = f"{pe_node} ex:hasSpecialComplication ex:NoOtherComplication ."

        # จัดการ Exercise Frequency
        freq_val = data.get('frequency') 
        freq_triple = ""
        if freq_val:
            freq_triple = f"ex:{pid} ex:exerciseFrequency ex:{escape_sparql(freq_val)} ."

        # จัดการ Favorites
        raw_favs = data.get('favorites')
        fav_triples = ""
        if isinstance(raw_favs, list):
            for fav in raw_favs:
                fav_triples += f"ex:{pid} ex:favoriteExercise ex:{escape_sparql(fav)} .\n"

        # 3. สร้าง Triples
        # 🔥 [เพิ่ม] ex:gender "{gender_val}" ; ลงไปในก้อนแรก
        triples = f"""
            ex:{pid} a ex:Patient ; 
                     ex:diabetType ex:{escape_sparql(data['type'])} ; 
                     ex:gender "{gender_val}" ;  
                     ex:insulinTreatment "{insulin_val}"^^xsd:boolean ;
                     ex:firstname "{fname}" ; ex:lastname "{lname}" ; 
                     ex:hasPhysicalExam {pe_node} ; ex:hasLabExam {le_node} .
            
            {freq_triple}
            {fav_triples}
            
            {pe_node} a ex:PhysicalExam ; 
                        ex:hasWeight "{val('weight')}"^^xsd:decimal ; 
                        ex:hasHeight "{val('height')}"^^xsd:decimal ; 
                        ex:hasBMI "{val('bmi')}"^^xsd:decimal ; 
                        ex:hasSBP "{int(val('sbp'))}"^^xsd:decimal ; 
                        ex:hasDBP "{int(val('dbp'))}"^^xsd:decimal .
            
            {special_triples} 
            
            {le_node} a ex:LabExam ; ex:hasTotalCholesterol "{val('chol')}"^^xsd:decimal ; 
                        ex:hasLDL "{val('ldl')}"^^xsd:decimal ; ex:hasHDL "{val('hdl')}"^^xsd:decimal ; 
                        ex:hasTriglyceride "{val('tri')}"^^xsd:decimal ;
                        ex:hasFPG "{val('fpg')}"^^xsd:decimal ; 
                        ex:hasKetone "{ketone_val}" ; ex:hasMicroalbuminurin "{micro_val}" . 
        """
        
        sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> INSERT DATA {{ {triples} }}")
        sparql_write.query()
        print(f"💾 Saved Raw Data for {pid} (Inc. Gender, Favorites & Frequency)")
        
    except Exception as e:
        print(f"❌ Error saving raw data: {e}")

def save_results_to_db(pid_num, recs, warns, comorbs, complis, avoids, intens, freqs):
    if not validate_id(pid_num): return
    pid = f"Patient{pid_num}"
    
    del_q = f"""
    PREFIX ex: <http://example.org/diabetes#> 
    DELETE {{ 
        ex:{pid} ex:hasPatientWarning ?w . 
        ex:{pid} ex:recommendedExercise ?r . 
        ex:{pid} ex:hasComorbidity ?c . 
        ex:{pid} ex:hasComplication ?cp .
        ex:{pid} ex:avoidExercise ?av .
        ex:{pid} ex:intensityOfExercise ?int .
        ex:{pid} ex:exerciseFrequency ?fr .
    }} 
    WHERE {{ 
        OPTIONAL {{ ex:{pid} ex:hasPatientWarning ?w }} 
        OPTIONAL {{ ex:{pid} ex:recommendedExercise ?r }} 
        OPTIONAL {{ ex:{pid} ex:hasComorbidity ?c }} 
        OPTIONAL {{ ex:{pid} ex:hasComplication ?cp }}
        OPTIONAL {{ ex:{pid} ex:avoidExercise ?av }}
        OPTIONAL {{ ex:{pid} ex:intensityOfExercise ?int }}
        OPTIONAL {{ ex:{pid} ex:exerciseFrequency ?fr }}
    }}"""
    sparql_write.setQuery(del_q); sparql_write.query()
    
    triples = []
    for x in recs: triples.append(f"ex:{pid} ex:recommendedExercise ex:{x} .")
    for x in warns: triples.append(f"ex:{pid} ex:hasPatientWarning ex:{x} .")
    for x in comorbs: triples.append(f"ex:{pid} ex:hasComorbidity ex:{x} .")
    for x in complis: triples.append(f"ex:{pid} ex:hasComplication ex:{x} .")
    
    for x in avoids: triples.append(f"ex:{pid} ex:avoidExercise ex:{x} .") 
    for x in intens: triples.append(f"ex:{pid} ex:intensityOfExercise ex:{x} .")
    for x in freqs: triples.append(f"ex:{pid} ex:exerciseFrequency ex:{x} .")
    
    if triples:
        ins_q = f"PREFIX ex: <http://example.org/diabetes#> INSERT DATA {{ {' '.join(triples)} }}"
        sparql_write.setQuery(ins_q); sparql_write.query()
        print(f"💾 Saved {len(triples)} results")

def delete_patient(patient_id):
    if not validate_id(patient_id): return
    pid = f"Patient{patient_id}"
    sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ?s ?p ?o . ?pe ?pp ?oo . ?le ?lp ?lo }} WHERE {{ ?s ?p ?o . FILTER(?s = ex:{pid}) OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} }}")
    sparql_write.query()

def get_patient_profile(patient_id):
    if not validate_id(patient_id): return None
    pid = f"Patient{patient_id}"
    
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?fname ?lname ?type ?weight ?height ?bmi ?sbp ?dbp ?chol ?ldl ?hdl ?tri ?fpg ?ketone ?micro 
           ?recName ?recInten ?recFreq 
           ?warnDesc ?comorbName ?compliName 
           ?fav ?specialRaw 
    WHERE {{
        ex:{pid} a ex:Patient ; ex:diabetType ?typeUri .
        BIND(STRAFTER(STR(?typeUri), "#") AS ?type)
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }} OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
        
        OPTIONAL {{ 
            ex:{pid} ex:hasPhysicalExam ?pe . 
            OPTIONAL {{ ?pe ex:hasWeight ?weight }} OPTIONAL {{ ?pe ex:hasHeight ?height }}
            OPTIONAL {{ ?pe ex:hasBMI ?bmi }} OPTIONAL {{ ?pe ex:hasSBP ?sbp }} OPTIONAL {{ ?pe ex:hasDBP ?dbp }} 
            OPTIONAL {{ ?pe ex:hasSpecialComplication ?sp1 }}
        }}

        OPTIONAL {{ ex:{pid} ex:hasSpecialComplication ?sp2 }}
        BIND(COALESCE(?sp1, ?sp2) AS ?specialRaw)

        OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . 
                    OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} 
                    OPTIONAL {{ ?le ex:hasHDL ?hdl }} OPTIONAL {{ ?le ex:hasTriglyceride ?tri }}
                    OPTIONAL {{ ?le ex:hasFPG ?fpg }} OPTIONAL {{ ?le ex:hasKetone ?ketone }} OPTIONAL {{ ?le ex:hasMicroalbuminurin ?micro }} }}
        
        OPTIONAL {{ ex:{pid} ex:favoriteExercise ?fav }}

        OPTIONAL {{ 
            ex:{pid} ex:recommendedExercise ?rec . 
            OPTIONAL {{ ?rec rdfs:label ?recLabel }} 
            BIND(COALESCE(?recLabel, STRAFTER(STR(?rec), "#")) AS ?recName)
            
            OPTIONAL {{ ?rec ex:intensityOfExercise ?intRaw . OPTIONAL {{ ?intRaw rdfs:label ?intLabel }}
                        BIND(COALESCE(?intLabel, STRAFTER(STR(?intRaw), "#"), STR(?intRaw)) AS ?recInten) }}
            
            OPTIONAL {{ ?rec ex:exerciseFrequency ?frqRaw . OPTIONAL {{ ?frqRaw rdfs:label ?frqLabel }}
                        BIND(COALESCE(?frqLabel, STRAFTER(STR(?frqRaw), "#"), STR(?frqRaw)) AS ?recFreq) }}
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
        "weight": first.get("weight", {}).get("value", "-"), "height": first.get("height", {}).get("value", "-"),
        "bmi": first.get("bmi", {}).get("value", "-"),
        "sbp": first.get("sbp", {}).get("value", "-"), "dbp": first.get("dbp", {}).get("value", "-"),
        "chol": first.get("chol", {}).get("value", "-"), "ldl": first.get("ldl", {}).get("value", "-"),
        "hdl": first.get("hdl", {}).get("value", "-"), "tri": first.get("tri", {}).get("value", "-"),
        "fpg": first.get("fpg", {}).get("value", "-"), "ketone": first.get("ketone", {}).get("value", "-"),
        "micro": first.get("micro", {}).get("value", "-"), 
    }

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
        final_exercises.append(f"{name} ({' | '.join(info_parts)})" if info_parts else name)

    def clean_val(val):
        if not val: return ""
        if "#" in val: return val.split('#')[-1]
        return val

    def extract_set(key): 
        return list(set([clean_val(r[key]["value"]) for r in bindings if key in r and r[key]["value"]]))

    return {
        "info": info, 
        "exercises": final_exercises, 
        "warnings": extract_set("warnDesc"), 
        "comorbs": extract_set("comorbName"), 
        "complis": extract_set("compliName"),
        "favorites": extract_set("fav"),
        "specials": extract_set("specialRaw")   
    }
    
def get_all_recommendations(patient_id):
    """
    ดึงรายการท่าออกกำลังกายแนะนำ 'ทั้งหมด' ของคนไข้คนนี้จาก GraphDB
    """
    if not validate_id(patient_id): return []
    pid = f"Patient{patient_id}"

    # เขียนคำสั่ง SPARQL เพื่อดึงทุกท่าที่สัมพันธ์กับ ex:recommendedExercise
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?recName 
    WHERE {{
        ex:{pid} ex:recommendedExercise ?rec .
        BIND(STRAFTER(STR(?rec), "#") AS ?recName)
    }}
    """
    
    try:
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()
        
        exercises = []
        for r in results["results"]["bindings"]:
            if "recName" in r:
                exercises.append(r["recName"]["value"])
        
        # ผลลัพธ์จะเป็น List เช่น ['Walking', 'Swimming', 'TaiChi']
        return exercises

    except Exception as e:
        print(f"❌ Error fetching recommendations: {e}")
        return []
    
def get_patient_latest_record(patient_id):
    """
    ดึงข้อมูลดิบของผู้ป่วยเพื่อนำไป Auto-fill ในหน้าแบบฟอร์ม
    """
    if not validate_id(patient_id): return {"found": False}
    pid = f"PatientSUPA{patient_id}"

    # ✅ เพิ่ม ?freq เข้าไปใน SELECT
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?fname ?lname ?gender ?type ?insulin
           ?weight ?height ?bmi ?sbp ?dbp 
           ?chol ?ldl ?hdl ?tri 
           ?fpg ?ketone ?micro ?date
           ?special ?fav ?freq
    WHERE {{
        ex:{pid} a ex:Patient .
        
        # ข้อมูลส่วนตัว
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }}
        OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
        OPTIONAL {{ ex:{pid} ex:gender ?gender }} 
        OPTIONAL {{ ex:{pid} ex:diabetType ?typeUri . BIND(STRAFTER(STR(?typeUri), "#") AS ?type) }}
        OPTIONAL {{ ex:{pid} ex:insulinTreatment ?insulin }}
        OPTIONAL {{ ex:{pid} ex:checkupDate ?date }}

        # ✅ เพิ่ม: ความถี่ออกกำลังกาย (Frequency)
        OPTIONAL {{ 
            ex:{pid} ex:exerciseFrequency ?freqUri . 
            BIND(STRAFTER(STR(?freqUri), "#") AS ?freq) 
        }}

        # ข้อมูลร่างกาย (Physical Exam)
        OPTIONAL {{ 
            ex:{pid} ex:hasPhysicalExam ?pe .
            OPTIONAL {{ ?pe ex:hasWeight ?weight }}
            OPTIONAL {{ ?pe ex:hasHeight ?height }}
            OPTIONAL {{ ?pe ex:hasBMI ?bmi }}
            OPTIONAL {{ ?pe ex:hasSBP ?sbp }}
            OPTIONAL {{ ?pe ex:hasDBP ?dbp }}
            # ดึง Special Complication
            OPTIONAL {{ ?pe ex:hasSpecialComplication ?spUri . BIND(STRAFTER(STR(?spUri), "#") AS ?special) }}
        }}

        # ข้อมูลผลเลือด (Lab Exam)
        OPTIONAL {{
            ex:{pid} ex:hasLabExam ?le .
            OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }}
            OPTIONAL {{ ?le ex:hasLDL ?ldl }}
            OPTIONAL {{ ?le ex:hasHDL ?hdl }}
            OPTIONAL {{ ?le ex:hasTriglyceride ?tri }}
            OPTIONAL {{ ?le ex:hasFPG ?fpg }}
            OPTIONAL {{ ?le ex:hasKetone ?ketone }}
            OPTIONAL {{ ?le ex:hasMicroalbuminurin ?micro }}
        }}

        # ดึงกิจกรรมที่ชอบ
        OPTIONAL {{ 
            ex:{pid} ex:favoriteExercise ?favUri . 
            BIND(STRAFTER(STR(?favUri), "#") AS ?fav) 
        }}
    }}
    """

    try:
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()
        bindings = results["results"]["bindings"]

        if not bindings:
            return {"found": False}

        # เตรียมตัวแปรเก็บข้อมูล
        data = {
            "found": True,
            "special": [],  # เตรียม List ไว้
            "favorites": [] # เตรียม List ไว้
        }

        def get_val(row, key):
            return row[key]["value"] if key in row else ""

        # วนลูปเพื่อรวบรวมข้อมูล
        for row in bindings:
            # ข้อมูลทั่วไป (เก็บทับได้เลย เพราะค่าเหมือนกันทุกบรรทัด)
            if "fname" in row: data["firstname"] = get_val(row, "fname")
            if "lname" in row: data["lastname"] = get_val(row, "lname")
            if "gender" in row: data["gender"] = get_val(row, "gender") # ✅ ดึงเพศ
            if "type" in row: data["diabetes_type"] = get_val(row, "type")
            if "insulin" in row: data["insulin_use"] = get_val(row, "insulin")
            if "date" in row: data["checkup_date"] = get_val(row, "date")
            
            # ✅ ดึงความถี่ออกกำลังกาย
            if "freq" in row: data["frequency"] = get_val(row, "freq")

            if "weight" in row: data["weight"] = get_val(row, "weight")
            if "height" in row: data["height"] = get_val(row, "height")
            # BMI
            if "sbp" in row: data["bp_high"] = get_val(row, "sbp")
            if "dbp" in row: data["bp_low"] = get_val(row, "dbp")

            if "chol" in row: data["cholesterol"] = get_val(row, "chol")
            if "ldl" in row: data["ldl"] = get_val(row, "ldl")
            if "hdl" in row: data["hdl"] = get_val(row, "hdl")
            if "tri" in row: data["triglyceride"] = get_val(row, "tri")
            if "fpg" in row: data["fpg"] = get_val(row, "fpg")
            if "ketone" in row: data["ketone"] = get_val(row, "ketone")
            if "micro" in row: data["microalbumin"] = get_val(row, "micro")

            # เก็บค่าที่เป็น List (ป้องกันค่าซ้ำ)
            if "special" in row:
                val = get_val(row, "special")
                if val and val not in data["special"]:
                    data["special"].append(val)
            
            if "fav" in row:
                val = get_val(row, "fav")
                if val and val not in data["favorites"]:
                    data["favorites"].append(val)

        return data

    except Exception as e:
        print(f"❌ Error fetching latest record: {e}")
        return {"found": False}