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
        # 1. ลบข้อมูลเก่า (แก้ให้ลบทุกอย่างที่ต่อจากคนไข้ เพื่อไม่ให้ค่า NoGeneralComplication เดิมค้าง)
        delete_query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            DELETE {{ 
                ex:{pid} ?p ?o . 
                ?pe ?pp ?oo . 
                ?le ?lp ?lo 
            }} 
            WHERE {{ 
                ex:{pid} ?p ?o . 
                OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} 
                OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} 
            }}
        """
        sparql_write.setQuery(delete_query)
        sparql_write.query()
        
        # 2. เตรียมข้อมูล
        fname = escape_sparql(data.get('firstname', '-'))
        lname = escape_sparql(data.get('lastname', '-'))
        gender_val = escape_sparql(data.get('gender', '-')) 
        pe_date = escape_sparql(data.get('checkup_date', ''))
        le_date = escape_sparql(data.get('blood_test_date', ''))

        insulin_val = escape_sparql(data.get('insulin_use') or "false")
        ketone_val = escape_sparql(data.get('ketone') or "Negative")
        micro_val = escape_sparql(data.get('micro') or "Negative")
        
        def val(k): return safe_float(data.get(k)) or 0

        # --- แก้ไขส่วนจัดการ Special Complication (เอา NoOtherComplication ออก) ---
        raw_special = data.get('special')
        special_triples = ""

        if isinstance(raw_special, list) and len(raw_special) > 0:
            for sp in raw_special:
                # บันทึกเฉพาะที่มีการเลือกจริง และไม่ใช่ค่า 'None' หรือค่าว่าง
                if sp and sp not in ["None", "", "NoOtherComplication"]:
                    special_triples += f"{pe_node} ex:hasSpecialComplication ex:{escape_sparql(sp)} .\n"
        elif isinstance(raw_special, str) and raw_special not in ["None", "", "NoOtherComplication"]:
            special_triples = f"{pe_node} ex:hasSpecialComplication ex:{escape_sparql(raw_special)} ."
        # --- ถ้าไม่มีการเลือก ปล่อยให้ special_triples ว่างไปเลย ไม่ต้องใส่ Default ---

        # จัดการ Frequency
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
                        ex:visitDate_Physical "{pe_date}"^^xsd:date ;
                        ex:hasWeight "{val('weight')}"^^xsd:decimal ; 
                        ex:hasHeight "{val('height')}"^^xsd:decimal ; 
                        ex:hasBMI "{val('bmi')}"^^xsd:decimal ; 
                        ex:hasSBP "{int(val('sbp'))}"^^xsd:decimal ; 
                        ex:hasDBP "{int(val('dbp'))}"^^xsd:decimal .
            
            {special_triples} 
            
            {le_node} a ex:LabExam ; 
                        ex:visitDate_Lab "{le_date}"^^xsd:date ;
                        ex:hasTotalCholesterol "{val('chol')}"^^xsd:decimal ; 
                        ex:hasLDL "{val('ldl')}"^^xsd:decimal ; ex:hasHDL "{val('hdl')}"^^xsd:decimal ; 
                        ex:hasTriglyceride "{val('tri')}"^^xsd:decimal ;
                        ex:hasFPG "{val('fpg')}"^^xsd:decimal ; 
                        ex:hasKetone "{ketone_val}" ; ex:hasMicroalbuminurin "{micro_val}" . 
        """
        
        sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> INSERT DATA {{ {triples} }}")
        sparql_write.query()
        print(f"💾 Saved Raw Data for {pid} (Cleaned & Updated)")
        
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
    pid = f"PatientSUPA{patient_id}"

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

    SELECT ?id ?name ?desc ?mets (GROUP_CONCAT(DISTINCT ?typeUri; separator=",") AS ?allTypes)
    WHERE {
        ?s a ?typeUri .
        ?typeUri rdfs:subClassOf* ex:Exercise . 
        FILTER(?typeUri != ex:Exercise)

        BIND(STRAFTER(STR(?s), "#") AS ?id)

        OPTIONAL { ?s rdfs:label ?name }
        OPTIONAL { ?s ex:description ?desc }
        OPTIONAL { ?s ex:metValue ?mets }
    }
    GROUP BY ?id ?name ?desc ?mets
    """
    try:
        sparql_read.setQuery(query)
        sparql_read.setReturnFormat(JSON)
        results = sparql_read.query().convert()
        
        exercises = []
        class_image_mapping = {
            "walking": "walking.png", "running": "running.png", 
            "dancing": "dancing.png", "bicycling": "cycling.png",
            "resistance": "resistance.png", "stretching": "flexibility.png",
            "aerobic": "aerobic.png", "wateractivity": "water.png"
        }

        for r in results["results"]["bindings"]:
            def val(key): return r[key]["value"] if key in r else ""
            
            # เก็บ Types ทั้งหมดไว้ใน Array
            types_list = val("allTypes").split(',')
            
            # --- Logic: เลือกคลาสที่เจาะจงที่สุด (ไม่ใช่ Aerobic ถ้ามี Walking) ---
            # เราจะตัด "Aerobic" ออกถ้าในรายการมีคลาสอื่นที่เจาะจงกว่าอยู่ด้วย
            specific_type = ""
            if len(types_list) > 1:
                # กรองเอาพวกคลาสทั่วไปอย่าง Aerobic ออก เพื่อเหลือตัวที่เจาะจง
                filtered_types = [t for t in types_list if "Aerobic" not in t]
                specific_type = filtered_types[0] if filtered_types else types_list[0]
            else:
                specific_type = types_list[0]

            raw_type_name = specific_type.split('#')[-1]
            
            # เลือกรูปภาพตามชื่อคลาสที่เจาะจง
            img_name = "exercise_default.png"
            for key, filename in class_image_mapping.items():
                if key in raw_type_name.lower():
                    img_name = filename
                    break

            exercises.append({
                "id": val("id"),
                "name": val("name") or val("id"),
                "original_type": specific_type, # ส่งตัวที่ Specific ที่สุดไป
                "all_categories": types_list,   # ส่งทั้งหมดไปเพื่อใช้ในการ Filter
                "img": f"/static/images/exercises/{img_name}",
                "mets": float(val("mets")) if val("mets") else 0,
                "desc": val("desc") or "ไม่มีรายละเอียดเพิ่มเติม"
            })
            
        return exercises
    except Exception as e:
        print(f"❌ Error: {e}")
        return []