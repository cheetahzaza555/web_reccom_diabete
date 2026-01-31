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

    # ✅ 1. สร้างตัวแปร raw_id (เฉพาะตัวเลข 99) และ pid (Patient99) แยกกันชัดเจน
    raw_id = str(data.get('id')).replace("Patient", "")  # ได้ "99"
    pid = f"Patient{raw_id}"                             # ได้ "Patient99"
    
    # ✅ 2. ใช้ raw_id ในการตั้งชื่อ Node (จะได้ชื่อสวยๆ ตามที่คุณต้องการ)
    pe_node = f"ex:PE1P00{raw_id}"   # -> ex:PE1P0099
    le_node = f"ex:LAB1P00{raw_id}"  # -> ex:LAB1P0099

    try:
        # ... (ส่วนลบข้อมูลเก่า เหมือนเดิม) ...
        sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ?s ?p ?o . ?pe ?pp ?oo . ?le ?lp ?lo }} WHERE {{ ?s ?p ?o . FILTER(?s = ex:{pid}) OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} }}")
        sparql_write.query()
        
        # ... (ส่วนเตรียมข้อมูล เหมือนเดิม) ...
        fname = escape_sparql(data.get('firstname', '-'))
        lname = escape_sparql(data.get('lastname', '-'))
        ketone_val = escape_sparql(data.get('ketone') or "Negative")
        micro_val = escape_sparql(data.get('micro') or "Negative")
        
        def val(k): return safe_float(data.get(k)) or 0

        # ... (ส่วนจัดการ Special / Frequency เหมือนเดิม) ...
        # (Copy logic เดิมของคุณมาวางตรงนี้ได้เลย)
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

        freq_val = data.get('frequency') 
        freq_triple = ""
        if freq_val:
            freq_triple = f"ex:{pid} ex:exerciseFrequency ex:{escape_sparql(freq_val)} ."

        # 3. สร้าง Triples (จุดนี้สำคัญ เช็คเรื่อง Data Type ให้ตรงกับ Ontology!)
        # หมายเหตุ: ถ้าใน Ontology คุณแก้ hasSBP เป็น xsd:decimal แล้ว โค้ดด้านล่างนี้ใช้ได้เลย
        # แต่ถ้า hasSBP ยังเป็น integer ต้องแก้ ^^xsd:decimal เป็น ^^xsd:integer เฉพาะบรรทัด sbp/dbp
        triples = f"""
            ex:{pid} a ex:Patient ; 
                     ex:diabetType ex:{escape_sparql(data['type'])} ; 
                     ex:firstname "{fname}" ; ex:lastname "{lname}" ; 
                     ex:hasPhysicalExam {pe_node} ; ex:hasLabExam {le_node} .
            
            {freq_triple}
            
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
        print(f"💾 Saved Raw Data for {pid} (Inc. Frequency)")
        
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
        return val.split('#')[-1] if '#' in val else val

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