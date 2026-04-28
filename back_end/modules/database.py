# modules/database.py
import re
import uuid
import datetime
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
    # 1. เช็ค description และ label ก่อน (เผื่อใน GraphDB มีข้อมูลภาษาไทยอยู่แล้ว)
    if hasattr(entity, "description") and entity.description: return str(entity.description[0])
    if hasattr(entity, "label") and entity.label: return str(entity.label[0])
    
    # 2. ถ้าใน GraphDB ไม่มี label ภาษาไทย ให้เอาชื่อ (name) มาดักแปลภาษา
    name_str = entity.name
    
    # พจนานุกรมแปลภาษา (เพิ่มคำอื่นๆ ที่ต้องการแปลได้ที่นี่เลย)
    translations = {
        "NoComorbidity": "ไม่มีโรคร่วม",
        "NoGeneralComplication": "ไม่มีภาวะแทรกซ้อนทั่วไป",
        "NoOtherComplication": "ไม่มีภาวะแทรกซ้อนอื่นๆ",
        "Retinopathy": "จอประสาทตาเสื่อม (Retinopathy)",
        "HeartDisease": "โรคหัวใจ (Heart Disease)",
        "PeripheralNeuropathy": "ปลายประสาทเสื่อม (Neuropathy)",
        "AutonomicNeuropathy": "ระบบประสาทอัตโนมัติผิดปกติ"
    }
    
    # เช็คว่าถ้าชื่อตรงกับใน Dictionary ให้แปลเป็นไทย ถ้าไม่ตรงให้ใช้ชื่อเดิม
    if name_str in translations:
        return translations[name_str]
        
    return name_str

def safe_get_name(uri):
    if not uri: return ""
    return re.split(r'[#/]', uri)[-1]

# --- Database Functions ---

def save_raw_patient_data(data):
    if not validate_id(data.get('id')): return

    # ตัด SUPA ออกป้องกันร่างโคลน
    raw_id = str(data.get('id')).replace("Patient", "").replace("SUPA", "")  
    pid = f"Patient{raw_id}"                                
    
    # คืนค่ากลับไปใช้ UUID แบบดั้งเดิมของคุณ
    pe_node = f"ex:PE_Node_{raw_id}_{uuid.uuid4().hex[:4]}" 
    le_node = f"ex:LE_Node_{raw_id}_{uuid.uuid4().hex[:4]}" 

    try:
        delete_query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            DELETE {{ 
                ex:{pid} ex:hasPhysicalExam ?pe . ex:{pid} ex:hasLabExam ?le .
                ex:{pid} ex:exerciseFrequency ?f . ex:{pid} ex:favoriteExercise ?fav .
                ?pe ?pp ?po . ?le ?lp ?lo .
            }} 
            WHERE {{ 
                OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?po }} 
                OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} 
                OPTIONAL {{ ex:{pid} ex:exerciseFrequency ?f }}
                OPTIONAL {{ ex:{pid} ex:favoriteExercise ?fav }}
            }}
        """
        sparql_write.setQuery(delete_query)
        sparql_write.query()
        
        pe_date = escape_sparql(data.get('checkup_date', ''))
        le_date = escape_sparql(data.get('blood_test_date', ''))
        
        def val(k, alt=None): 
            v = data.get(k) or data.get(alt)
            return safe_float(v) or 0

        pe_date_line = f'ex:visitDate_Physical "{pe_date}"^^xsd:date ;' if pe_date else ""
        le_date_line = f'ex:visitDate_Lab "{le_date}"^^xsd:date ;' if le_date else ""

        raw_special = data.get('special')
        special_triples = ""
        if isinstance(raw_special, list):
            for sp in raw_special:
                if sp and sp not in ["None", "", "NoOtherComplication"]:
                    special_triples += f"{pe_node} ex:hasSpecialComplication ex:{escape_sparql(sp)} .\n"
        
        freq_val = data.get('frequency')
        freq_triple = f"ex:{pid} ex:exerciseFrequency ex:{escape_sparql(freq_val)} ." if freq_val else ""
        
        raw_favs = data.get('favorites') or []
        fav_triples = ""
        for fav in raw_favs:
            if fav: fav_triples += f"ex:{pid} ex:favoriteExercise ex:{escape_sparql(fav)} .\n"

        # ป้องกัน Reasoner พังจากค่าอินซูลินที่เป็น None
        raw_insulin = str(data.get('insulin_use')).lower()
        safe_insulin = "true" if raw_insulin == "true" else "false"

        # โค้ดสร้าง Triples แบบเดิมของคุณ (ใช้ตัว 'a' ไม่ใช่ 'rdf:type')
        triples = f"""
            ex:{pid} a ex:Patient ; 
                     ex:diabetType ex:{escape_sparql(data.get('type', 'T2DM'))} ; 
                     ex:gender "{escape_sparql(data.get('gender', '-'))}" ;  
                     ex:insulinTreatment "{safe_insulin}"^^xsd:boolean ;
                     ex:hasPhysicalExam {pe_node} ; ex:hasLabExam {le_node} .
            
            {freq_triple} {fav_triples}
            
            {pe_node} a ex:PhysicalExam ; 
                        {pe_date_line}
                        ex:hasWeight "{val('weight')}"^^xsd:decimal ; 
                        ex:hasHeight "{val('height')}"^^xsd:decimal ; 
                        ex:hasBMI "{val('bmi')}"^^xsd:decimal ; 
                        ex:hasSBP "{int(val('bp_high', 'sbp'))}"^^xsd:decimal ; 
                        ex:hasDBP "{int(val('bp_low', 'dbp'))}"^^xsd:decimal .
            
            {special_triples} 
            
            {le_node} a ex:LabExam ; 
                        {le_date_line}
                        ex:hasTotalCholesterol "{val('cholesterol', 'chol')}"^^xsd:decimal ; 
                        ex:hasLDL "{val('ldl')}"^^xsd:decimal ; ex:hasHDL "{val('hdl')}"^^xsd:decimal ; 
                        ex:hasTriglyceride "{val('triglyceride', 'tri')}"^^xsd:decimal ;
                        ex:hasFPG "{val('fpg')}"^^xsd:decimal ; 
                        ex:hasKetone "{data.get('ketone', 'Negative')}" ; 
                        ex:hasMicroalbuminurin "{data.get('micro', 'Negative')}" . 
        """
        
        sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> INSERT DATA {{ {triples} }}")
        sparql_write.query()
        print(f"💾 Saved Raw Data for {pid}")
        
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
    
# ในไฟล์ database.py

def get_all_recommendations(patient_id):
    """
    ดึงรายการท่าออกกำลังกายแนะนำ พร้อมรายละเอียด (ชื่อ, ความหนัก, ประเภท)
    """
    # 1. จัดการเรื่อง ID ให้ถูกต้อง (แก้จุดตายตรงนี้)
    # ถ้าส่งมาเป็น "PatientSUPA11" ให้ใช้เลย แต่ถ้าส่งมาแค่ "SUPA11" ให้เติม "Patient"
    clean_id = patient_id.replace("Patient", "") # ลบออกก่อนกันเหนียว
    pid_resource = f"Patient{clean_id}" # แล้วเติมเข้าไปใหม่ให้มีแค่ 1 อันเสมอ
    
    # หรือถ้าใน DB คุณชื่อ "Patient_Mem_SUPA..." ให้แก้บรรทัดบนเป็น:
    # pid_resource = f"Patient_Mem_{clean_id}" 
    # (ให้ดูใน GraphDB ว่าชื่อ Resource จริงๆ คืออะไร)

    print(f"🔍 Searching GraphDB for: ex:{pid_resource}") # ดู Log ว่าหาชื่อถูกไหม

    # 2. คำสั่ง SPARQL (ตรวจสอบชื่อ Property ให้ตรงเป๊ะๆ)
    # เช็คใน GraphDB ว่าใช้ 'recommendedExercise' หรือ 'recommendExercise'
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?recId ?label ?met ?categoryName
    WHERE {{
        # ใช้ UNION เพื่อกันเหนียวเรื่องชื่อ Property (บางทีพิมพ์ผิด)
        {{ ex:{pid_resource} ex:recommendedExercise ?rec . }}
        UNION
        {{ ex:{pid_resource} ex:recommendExercise ?rec . }}
        
        BIND(STRAFTER(STR(?rec), "#") AS ?recId)

        OPTIONAL {{ ?rec rdfs:label ?label . }}
        OPTIONAL {{ ?rec ex:metValue ?met . }}
        OPTIONAL {{ 
            ?rec ex:hasKindOfExercise ?kind .
            BIND(STRAFTER(STR(?kind), "#") AS ?categoryName)
        }}
    }}
    """
    
    try:
        sparql_read.setQuery(query)
        sparql_read.setReturnFormat(JSON)
        results = sparql_read.query().convert()
        
        exercises_data = []
        
        # Mapping ภาษาไทย
        cat_map = {
            "Running": "การวิ่ง (Running)",
            "Walking": "การเดิน (Walking)",
            "Bicycling": "จักรยาน (Bicycling)",
            "WaterActivity": "กิจกรรมทางน้ำ",
            "Aerobic": "แอโรบิก",
            "Resistance": "แรงต้าน",
            "StretchingExercise": "ยืดเหยียด",
            "WeightBearingAerobicExercise": "แอโรบิกลงน้ำหนัก",
            "NonWeightBearingAerobicExercise": "แอโรบิกไม่ลงน้ำหนัก"
        }

        for r in results["results"]["bindings"]:
            ex_id = r["recId"]["value"]
            ex_name = r["label"]["value"] if "label" in r else ex_id
            ex_met = r["met"]["value"] if "met" in r else "-"
            
            raw_cat = r["categoryName"]["value"] if "categoryName" in r else "ทั่วไป"
            ex_cat = cat_map.get(raw_cat, raw_cat)

            exercises_data.append({
                "id": ex_id,
                "name": ex_name,
                "met": ex_met,
                "category": ex_cat
            })
        
        print(f"✅ Found {len(exercises_data)} exercises")
        return exercises_data

    except Exception as e:
        print(f"❌ Error fetching recommendations: {e}")
        return []
    
def get_patient_latest_record(patient_id):
    """
    ดึงข้อมูลดิบของผู้ป่วยเพื่อนำไป Auto-fill ในหน้าแบบฟอร์ม
    """
    if not validate_id(patient_id): return {"found": False}
    clean_id = str(patient_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}" # ✅ แก้เป็นแบบนี้

    # ✅ เพิ่ม ?datePE และ ?dateLab ใน SELECT
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?fname ?lname ?gender ?type ?insulin
           ?weight ?height ?bmi ?sbp ?dbp 
           ?chol ?ldl ?hdl ?tri 
           ?fpg ?ketone ?micro 
           ?datePE ?dateLab  
           ?special ?fav ?freq
    WHERE {{
        ex:{pid} a ex:Patient .
        
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }}
        OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
        OPTIONAL {{ ex:{pid} ex:gender ?gender }} 
        OPTIONAL {{ ex:{pid} ex:diabetType ?typeUri . BIND(STRAFTER(STR(?typeUri), "#") AS ?type) }}
        OPTIONAL {{ ex:{pid} ex:insulinTreatment ?insulin }}
        
        OPTIONAL {{ 
            ex:{pid} ex:exerciseFrequency ?freqUri . 
            BIND(STRAFTER(STR(?freqUri), "#") AS ?freq) 
        }}

        # ข้อมูลร่างกาย
        OPTIONAL {{ 
            ex:{pid} ex:hasPhysicalExam ?pe .
            OPTIONAL {{ ?pe ex:visitDate_Physical ?datePE }} # ✅ ดึงวันที่ตรวจร่างกาย
            OPTIONAL {{ ?pe ex:hasWeight ?weight }}
            OPTIONAL {{ ?pe ex:hasHeight ?height }}
            OPTIONAL {{ ?pe ex:hasBMI ?bmi }}
            OPTIONAL {{ ?pe ex:hasSBP ?sbp }}
            OPTIONAL {{ ?pe ex:hasDBP ?dbp }}
            OPTIONAL {{ ?pe ex:hasSpecialComplication ?spUri . BIND(STRAFTER(STR(?spUri), "#") AS ?special) }}
        }}

        # ข้อมูลผลเลือด
        OPTIONAL {{
            ex:{pid} ex:hasLabExam ?le .
            OPTIONAL {{ ?le ex:visitDate_Lab ?dateLab }}     # ✅ ดึงวันที่เจาะเลือด
            OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }}
            OPTIONAL {{ ?le ex:hasLDL ?ldl }}
            OPTIONAL {{ ?le ex:hasHDL ?hdl }}
            OPTIONAL {{ ?le ex:hasTriglyceride ?tri }}
            OPTIONAL {{ ?le ex:hasFPG ?fpg }}
            OPTIONAL {{ ?le ex:hasKetone ?ketone }}
            OPTIONAL {{ ?le ex:hasMicroalbuminurin ?micro }}
        }}

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

        data = {
            "found": True,
            "special": [],
            "favorites": []
        }

        def get_val(row, key):
            return row[key]["value"] if key in row else ""

        for row in bindings:
            if "fname" in row: data["firstname"] = get_val(row, "fname")
            if "lname" in row: data["lastname"] = get_val(row, "lname")
            if "gender" in row: data["gender"] = get_val(row, "gender")
            if "type" in row: data["diabetes_type"] = get_val(row, "type")
            if "insulin" in row: data["insulin_use"] = get_val(row, "insulin")
            if "freq" in row: data["frequency"] = get_val(row, "freq")

            # 🔥 แมพค่ากลับไปยังชื่อตัวแปรที่ HTML Form ใช้
            if "datePE" in row: data["checkup_date"] = get_val(row, "datePE")
            if "dateLab" in row: data["blood_test_date"] = get_val(row, "dateLab")

            if "weight" in row: data["weight"] = get_val(row, "weight")
            if "height" in row: data["height"] = get_val(row, "height")
            if "sbp" in row: data["bp_high"] = get_val(row, "sbp")
            if "dbp" in row: data["bp_low"] = get_val(row, "dbp")

            if "chol" in row: data["cholesterol"] = get_val(row, "chol")
            if "ldl" in row: data["ldl"] = get_val(row, "ldl")
            if "hdl" in row: data["hdl"] = get_val(row, "hdl")
            if "tri" in row: data["triglyceride"] = get_val(row, "tri")
            if "fpg" in row: data["fpg"] = get_val(row, "fpg")
            if "ketone" in row: data["ketone"] = get_val(row, "ketone")
            if "micro" in row: data["microalbumin"] = get_val(row, "micro")

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
    
# ในไฟล์ database.py

def get_exercise_details_by_id(exercise_id):
    """
    ดึงรายละเอียดของท่าออกกำลังกาย 1 ท่า (จาก ID) เพื่อเอาไปแสดงผล (Preview)
    """
    # เช็คว่า ID มี prefix ไหม
    if "http" in exercise_id:
        ex_resource = f"<{exercise_id}>"
    else:
        ex_resource = f"ex:{exercise_id}"

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?label ?met ?categoryName
    WHERE {{
        # ดึงข้อมูลตรงๆ จาก Resource ของท่านั้นเลย
        {ex_resource} rdfs:label ?label .
        OPTIONAL {{ {ex_resource} ex:metValue ?met . }}
        OPTIONAL {{ 
            {ex_resource} ex:hasKindOfExercise ?kind .
            BIND(STRAFTER(STR(?kind), "#") AS ?categoryName)
        }}
    }}
    LIMIT 1
    """
    
    try:
        sparql_read.setQuery(query)
        sparql_read.setReturnFormat(JSON)
        results = sparql_read.query().convert()
        
        if results["results"]["bindings"]:
            r = results["results"]["bindings"][0]
            
            # แปลหมวดหมู่ (ถ้าต้องการ)
            cat_map = { "Running": "การวิ่ง", "Walking": "การเดิน", "Bicycling": "จักรยาน" } # เพิ่มได้
            raw_cat = r["categoryName"]["value"] if "categoryName" in r else "ทั่วไป"
            
            return {
                "id": exercise_id,
                "name": r["label"]["value"],
                "met": r["met"]["value"] if "met" in r else "-",
                "category": cat_map.get(raw_cat, raw_cat)
            }
        else:
            return None
    except Exception as e:
        print(f"❌ Error getting exercise details: {e}")
        return None
    
def get_all_exercises_for_library():
    query = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    # เพิ่ม ?youtube_id เข้าไปใน SELECT และ GROUP BY
    SELECT ?id ?name  ?mets ?youtube_id (GROUP_CONCAT(DISTINCT ?typeUri; separator=",") AS ?allTypes)
    WHERE {
        ?s a ?typeUri .
        ?typeUri rdfs:subClassOf* ex:Exercise . 
        FILTER(?typeUri != ex:Exercise)

        BIND(STRAFTER(STR(?s), "#") AS ?id)
        OPTIONAL { ?s rdfs:label ?name }
        OPTIONAL { ?s ex:metValue ?mets }
        
        # แก้ไขจุดนี้: ใช้ ?s (ซึ่งคือตัวแปรของ Instance) และใช้ Prefix ex: ให้ถูกต้อง
        OPTIONAL { ?s ex:hasYoutubeID ?youtube_id }
    }
    # ต้องเพิ่ม ?youtube_id ใน GROUP BY ด้วยเพื่อให้ Query สมบูรณ์
    GROUP BY ?id ?name ?mets ?youtube_id
    """
    try:
        sparql_read.setQuery(query)
        sparql_read.setReturnFormat(JSON)
        results = sparql_read.query().convert()
        
        exercises = []
        
        # 1. ปรับลำดับความสำคัญใหม่: เอาตัวที่ "ยาวและเจาะจง" ไว้บนสุด 
        # เพื่อให้มันเลือก NonWeight ก่อน Weight หากท่านั้นเป็นทั้งคู่
        priority_order = [
            "NonWeightBearingAerobicSport", "WeightBearingAerobicSport",
            "NonWeightBearingResistanceExercise", "WeightBearingResistanceExercise",
            "Walking", "Running", "Dancing", "Bicycling", "WaterActivity",
            "Aerobic", "Resistance", "StretchingExercise"
        ]

        # 2. Mapping ชื่อคลาสกับไฟล์รูปภาพ (ต้องตรงกับชื่อไฟล์ในเครื่อง)
        img_map = {
            "nonweightbearingaerobicsport": "non_weight_sport.png",
            "weightbearingaerobicsport": "weight_sport.png",
            "nonweightbearingresistanceexercise": "non_weight_resistance.png",
            "weightbearingresistanceexercise": "weight_resistance.png",      
            "walking": "walking.png",
            "running": "running.png",
            "dancing": "dancing.png",
            "bicycling": "cycling.png",
            "wateractivity": "water.png",
            "stretching": "flexibility.png",
            "aerobic": "aerobic.png",
            "resistance": "resistance.png"
        }

        for r in results["results"]["bindings"]:
            def val(key): return r[key]["value"] if key in r else ""
            
            types_list = val("allTypes").split(',')
            raw_names = [t.split('#')[-1] for t in types_list]
            
            chosen_name = ""
            for p_name in priority_order:
                if p_name in raw_names:
                    chosen_name = p_name
                    break
            if not chosen_name: chosen_name = raw_names[0]
            
            search_key = chosen_name.lower()
            img_file = "exercise_default.png"

            if search_key in img_map:
                img_file = img_map[search_key]
            else:
                # Fallback: ค้นหาตัวที่ยาวที่สุดที่แมตช์ได้
                sorted_keys = sorted(img_map.keys(), key=len, reverse=True)
                for k in sorted_keys:
                    if k in search_key:
                        img_file = img_map[k]
                        break

            exercises.append({
                "id": val("id"),
                "name": val("name") or val("id"),
                "original_type": chosen_name,
                "all_categories": raw_names,
                "img": f"/static/images/exercises/{img_file}",
                "mets": float(val("mets")) if val("mets") else 0,
                "youtube_id": val("youtube_id") if val("youtube_id") else ""
            })
            
        return exercises
    except Exception as e:
        print(f"❌ Error in Backend: {e}")
        return []
    
    
def get_exercise_by_id(ex_id):
    print(f"👉 เช็กค่า exercise_id ที่รับมา: '{ex_id}'")
    # 1. เพิ่ม ?youtube_id เข้าไปใน SELECT และ GROUP BY
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?desc ?mets ?youtube_id  # <--- เพิ่ม ?youtube_id ตรงนี้
            (GROUP_CONCAT(DISTINCT ?typeUri; separator=",") AS ?allTypes)
            (GROUP_CONCAT(DISTINCT ?step; separator="|") AS ?stepsRaw)
            (GROUP_CONCAT(DISTINCT ?precaution; separator="|") AS ?precautionsRaw)
    WHERE {{
        BIND(ex:{ex_id} AS ?s)
        ?s rdfs:label ?name .
        ?s a ?typeUri .
        ?typeUri rdfs:subClassOf* ex:Exercise .
        FILTER(?typeUri != ex:Exercise)
        
        # ดึงรายละเอียดพื้นฐาน
        OPTIONAL {{ ?s ex:description ?desc }}
        OPTIONAL {{ ?s ex:metValue ?mets }}
        
        # ดึง Youtube ID จาก Instance (เหมือนในรูป image_4ec3c2.png)
        OPTIONAL {{ ?s ex:hasYoutubeID ?youtube_id }} # <--- เพิ่มบรรทัดนี้

        # ดึง Steps และ Precaution
        OPTIONAL {{ 
            ?source ex:hasStep ?step .
            FILTER(?source = ?s || ?source = ?typeUri)
        }}
        OPTIONAL {{ 
            ?source ex:hasPrecaution ?precaution .
            FILTER(?source = ?s || ?source = ?typeUri)
        }}
    }}
    GROUP BY ?name ?desc ?mets ?youtube_id # <--- เพิ่ม ?youtube_id ตรงนี้
    """

    try:
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()
        
        if not results["results"]["bindings"]:
            return None

        r = results["results"]["bindings"][0]
        def val(key): return r[key]["value"] if key in r else ""

        # --- ส่วนการจัดการหมวดหมู่และรูปภาพคงเดิม ---
        types_list = val("allTypes").split(',')
        raw_names = [t.split('#')[-1] for t in types_list]
        priority_order = [
            "NonWeightBearingAerobicSport", "WeightBearingAerobicSport",
            "NonWeightBearingResistanceExercise", "WeightBearingResistanceExercise",
            "Walking", "Running", "Dancing", "Bicycling", "WaterActivity",
            "Aerobic", "Resistance", "StretchingExercise"
        ]
        chosen_name = next((p for p in priority_order if p in raw_names), raw_names[0])
        img_map = {
            "nonweightbearingaerobicsport": "non_weight_sport.png",
            "weightbearingaerobicsport": "weight_sport.png",
            "nonweightbearingresistanceexercise": "non_weight_resistance.png",
            "weightbearingresistanceexercise": "weight_resistance.png",      
            "walking": "walking.png",
            "running": "running.png",
            "dancing": "dancing.png",
            "bicycling": "cycling.png",
            "wateractivity": "water.png",
            "stretchingexercise": "flexibility.png",
            "aerobic": "aerobic.png",
            "resistance": "resistance.png"
        }
        img_file = img_map.get(chosen_name.lower(), "exercise_default.png")


        yt_id = val("youtube_id")

        steps_list = val("stepsRaw").split('|') if val("stepsRaw") else []
        precautions_list = val("precautionsRaw").split('|') if val("precautionsRaw") else []
        steps = [s for s in steps_list if s.strip()]
        precautions = [p for p in precautions_list if p.strip()]

        return {
            "id": ex_id,
            "name": val("name") or ex_id,
            "original_type": chosen_name,
            "all_categories": raw_names,
            "img": f"/static/images/exercises/{img_file}",
            "mets": val("mets"),
            "desc": val("desc") or "ไม่มีรายละเอียดเพิ่มเติม",
            "steps": steps if steps else ["ไม่มีระบุขั้นตอน"], 
            "precaution": precautions[0] if precautions else "ไม่มีระบุข้อควรระวังพิเศษ",
            "video": yt_id # <--- ส่งค่า video_url กลับไปให้ HTML
        }

    except Exception as e:
        print(f"Error in get_exercise_by_id: {e}")
        return None
    
def register_new_patient(username, password_hash, firstname, lastname, email, role="user"):
    if not username or not password_hash:
        return {"success": False, "message": "ข้อมูลไม่ครบถ้วน"}
        
    new_id = str(uuid.uuid4())[:8]
    pid = f"Patient{new_id}"
    created_at = datetime.datetime.now().isoformat()
    
    check_query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    ASK {{ ?p ex:username "{escape_sparql(username)}" . }}
    """
    try:
        sparql_read.setQuery(check_query)
        if sparql_read.query().convert().get("boolean", False):
            return {"success": False, "message": "Username นี้มีผู้ใช้งานแล้ว"}
            
        insert_query = f"""
        PREFIX ex: <http://example.org/diabetes#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        INSERT DATA {{
            ex:{pid} a ex:Patient ;
                     ex:username "{escape_sparql(username)}" ;
                     ex:passwordHash "{escape_sparql(password_hash)}" ;
                     ex:firstname "{escape_sparql(firstname)}" ;
                     ex:lastname "{escape_sparql(lastname)}" ;
                     ex:email "{escape_sparql(email)}" ;
                     ex:role "{escape_sparql(role)}" ;
                     ex:createdAt "{created_at}"^^xsd:dateTime .
        }}
        """
        sparql_write.setQuery(insert_query)
        sparql_write.query()
        return {"success": True, "patient_id": pid}
    except Exception as e:
        return {"success": False, "message": str(e)}
    
def get_user_for_login(username):
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?patient ?passwordHash ?role ?fname ?lname
    WHERE {{
        ?patient a ex:Patient .
        ?patient ex:username "{escape_sparql(username)}" .
        ?patient ex:passwordHash ?passwordHash .
        OPTIONAL {{ ?patient ex:role ?role }}
        OPTIONAL {{ ?patient ex:firstname ?fname }}
        OPTIONAL {{ ?patient ex:lastname ?lname }}
    }} LIMIT 1
    """
    try:
        sparql_read.setQuery(query)
        bindings = sparql_read.query().convert()["results"]["bindings"]
        if not bindings: return None
            
        r = bindings[0]
        full_uri = r["patient"]["value"]
        pid = full_uri.split("#Patient")[-1]
        
        return {
            "patient_id": pid,
            "username": username,
            "password_hash": r["passwordHash"]["value"],
            "role": r.get("role", {}).get("value", "user"),
            "firstname": r.get("fname", {}).get("value", ""),
            "lastname": r.get("lname", {}).get("value", "")
        }
    except Exception as e:
        print(f"Error login: {e}")
        return None
    
def get_user_by_id(user_id):
    clean_id = str(user_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?username ?role ?fname ?lname
    WHERE {{
        ex:{pid} a ex:Patient .
        OPTIONAL {{ ex:{pid} ex:username ?username }}
        OPTIONAL {{ ex:{pid} ex:role ?role }}
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }}
        OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
    }} LIMIT 1
    """
    try:
        sparql_read.setQuery(query)
        res = sparql_read.query().convert()
        bindings = res["results"]["bindings"]
        if not bindings: return None
        
        r = bindings[0]
        # ✅ แก้ไขการดึงค่าให้ตรงกับชื่อตัวแปรใน SELECT (?fname, ?lname)
        # และใช้ Key ที่ Frontend รอรับอยู่ (firstname, lastname)
        return {
            "id": user_id,
            "username": r.get("username", {}).get("value", ""),
            "role": r.get("role", {}).get("value", "user"),
            "firstname": r.get("fname", {}).get("value", ""), # ต้องใช้ fname จาก SPARQL
            "lastname": r.get("lname", {}).get("value", "")   # ต้องใช้ lname จาก SPARQL
        }
    except Exception as e:
        print(f"Error in get_user_by_id: {e}")
        return None
    
# --- ฟังก์ชันจัดการตารางออกกำลังกาย (Plan Management) ---

def generate_30_days_plan(patient_id, exercise_id, exact_dates_list, daily_target_minutes):
    print(f"👉 เช็กค่า exercise_id ที่รับมา: '{exercise_id}'")
    pid = f"Patient{patient_id}" # ใช้ ID ดั้งเดิม
    start_date = datetime.datetime.today().date()
    
    # คืนค่ารหัส UUID ให้เหมือนเดิมที่คุณเขียนไว้
    run_id = str(uuid.uuid4())[:8]
    monthly_node = f"ex:MonthlyPlan_{pid}_{run_id}"
    
    current_month = start_date.month
    current_year = start_date.year
    
    triples = f"""
        {monthly_node} a ex:MonthlyPlan ;
            ex:planMonth "{current_month}"^^xsd:integer ;
            ex:planYear "{current_year}"^^xsd:integer ;
            ex:planName "แผน 30 วันเริ่มต้น" .
        ex:{pid} ex:hasMonthlyPlan {monthly_node} .
    """
    
    current_weekly_node = ""
    for i in range(30):
        current_date = start_date + datetime.timedelta(days=i)
        
        if i % 7 == 0:
            week_num = (i // 7) + 1
            current_weekly_node = f"ex:WeeklyPlan_{pid}_{run_id}_W{week_num}"
            triples += f"""
                {current_weekly_node} a ex:WeeklyPlan ;
                    ex:weekNumber "{week_num}"^^xsd:integer .
                {monthly_node} ex:hasWeeklyPlan {current_weekly_node} .
            """
            
        day_node = f"ex:DailyPlan_{pid}_{run_id}_Day{i+1}"
        date_str = current_date.isoformat()
        
        is_exercise = current_date in exact_dates_list
        status = "Pending" if is_exercise else "Rest"
        target_mins = daily_target_minutes if is_exercise else 0
        
        triples += f"""
            {day_node} a ex:DailyPlan ;
                ex:planDate "{date_str}"^^xsd:date ;
                ex:planStatus "{status}" ;
                ex:durationMinutes "{target_mins}"^^xsd:integer .
            {current_weekly_node} ex:hasDailyPlan {day_node} .
        """
        
        if is_exercise:
            triples += f"{day_node} ex:hasScheduledExercise ex:{escape_sparql(exercise_id)} .\n"

    insert_query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT DATA {{ {triples} }}
    """
    try:
        sparql_write.setQuery(insert_query)
        sparql_write.query()
        return True
    except Exception as e:
        print(f"❌ Error generating 30 days plan: {e}")
        return False

def get_dashboard_schedule(patient_id):
    """
    ดึงตารางรายวันมาโชว์บน Dashboard (เรียงตามวันที่)
    """
    pid = f"Patient{patient_id}"
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?dayNode ?date ?status ?duration ?exName ?exId
    WHERE {{
        ex:{pid} ex:hasMonthlyPlan ?month .
        ?month ex:hasWeeklyPlan ?week .
        ?week ex:hasDailyPlan ?dayNode .
        
        ?dayNode ex:planDate ?date .
        OPTIONAL {{ ?dayNode ex:planStatus ?status }}
        OPTIONAL {{ ?dayNode ex:durationMinutes ?duration }}
        
        OPTIONAL {{ 
            ?dayNode ex:hasScheduledExercise ?ex .
            BIND(STRAFTER(STR(?ex), "#") AS ?exId)
            OPTIONAL {{ ?ex rdfs:label ?label }}
            BIND(COALESCE(?label, ?exId) AS ?exName)
        }}
    }}
    ORDER BY ?date
    """
    try:
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()["results"]["bindings"]
        
        schedule = []
        for i, r in enumerate(results):
            # แยก URI เอาเฉพาะ ID เช่น DailyPlan_123_Day1
            day_id = safe_get_name(r["dayNode"]["value"])
            date_str = r["date"]["value"]
            status = r.get("status", {}).get("value", "Rest")
            duration = int(r.get("duration", {}).get("value", 0))
            ex_name = r.get("exName", {}).get("value", None)
            ex_original_id = r.get("exId", {}).get("value", None)
            
            is_exercise_day = status in ["Pending", "Completed"]
            is_completed = (status == "Completed")
            
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            
            schedule.append({
                "id": day_id,  # ใช้ชื่อ Node แทน ID ใน SQL
                "day_of_week": date_obj.weekday(),
                "is_exercise_day": is_exercise_day,
                "exercise_name": ex_name,
                "exercise_id": ex_original_id, # เก็บ ID ท่าไว้ใช้ตอนกดเข้าไปดูวิดีโอ
                "completed": is_completed,
                "duration_minutes": duration,
                "date_obj": date_obj
            })
        return schedule
    except Exception as e:
        print(f"❌ Error fetching schedule: {e}")
        return []

def delete_user_schedule(patient_id):
    """
    ลบตารางเก่าทั้งหมดของคนไข้ก่อนสร้างใหม่ (เทียบเท่า reset_plan)
    """
    pid = f"Patient{patient_id}"
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    DELETE {{
        ex:{pid} ex:hasMonthlyPlan ?m .
        ?m ?mp ?mo .
        ?w ?wp ?wo .
        ?d ?dp ?do .
    }}
    WHERE {{
        ex:{pid} ex:hasMonthlyPlan ?m .
        OPTIONAL {{ ?m ?mp ?mo }}
        OPTIONAL {{ ?m ex:hasWeeklyPlan ?w . ?w ?wp ?wo }}
        OPTIONAL {{ ?m ex:hasWeeklyPlan ?w . ?w ex:hasDailyPlan ?d . ?d ?dp ?do }}
    }}
    """
    try:
        sparql_write.setQuery(query)
        sparql_write.query()
        return True
    except Exception as e:
        print(f"❌ Error deleting schedule: {e}")
        return False

def update_daily_plan_status(day_node_id, is_completed, actual_duration=None):
    """
    อัปเดตสถานะของวันนั้นๆ ว่าทำเสร็จแล้ว และบันทึกเวลาที่ทำจริง
    """
    status = "Completed" if is_completed else "Pending"
    
    # ถ้าส่งเวลามาด้วย ให้อัปเดตเวลาด้วย
    duration_update = ""
    if actual_duration is not None:
        duration_update = f"""
        OPTIONAL {{ ex:{day_node_id} ex:durationMinutes ?oldDur }}
        """
        
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    
    DELETE {{
        ex:{day_node_id} ex:planStatus ?oldStatus .
        {f"ex:{day_node_id} ex:durationMinutes ?oldDur ." if actual_duration is not None else ""}
    }}
    INSERT {{
        ex:{day_node_id} ex:planStatus "{status}" .
        {f"ex:{day_node_id} ex:durationMinutes '{actual_duration}'^^xsd:integer ." if actual_duration is not None else ""}
    }}
    WHERE {{
        ex:{day_node_id} ex:planStatus ?oldStatus .
        {duration_update}
    }}
    """
    try:
        sparql_write.setQuery(query)
        sparql_write.query()
        return True
    except Exception as e:
        print(f"❌ Error updating status: {e}")
        return False
        
def get_daily_plan_info(day_node_id):
    """
    ดึงข้อมูลเฉพาะ 1 วัน สำหรับหน้า Start / Active Exercise
    """
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?status ?duration ?exName ?exId
    WHERE {{
        OPTIONAL {{ ex:{day_node_id} ex:planStatus ?status }}
        OPTIONAL {{ ex:{day_node_id} ex:durationMinutes ?duration }}
        OPTIONAL {{ 
            ex:{day_node_id} ex:hasScheduledExercise ?ex .
            BIND(STRAFTER(STR(?ex), "#") AS ?exId)
            OPTIONAL {{ ?ex rdfs:label ?label }}
            BIND(COALESCE(?label, ?exId) AS ?exName)
        }}
    }} LIMIT 1
    """
    try:
        sparql_read.setQuery(query)
        res = sparql_read.query().convert()["results"]["bindings"]
        if not res: return None
        
        r = res[0]
        return {
            "exercise_name": r.get("exName", {}).get("value", ""),
            "exercise_id": r.get("exId", {}).get("value", ""),
            "completed": r.get("status", {}).get("value", "") == "Completed",
            "target_minutes": int(r.get("duration", {}).get("value", 30))
        }
    except Exception as e:
        return None