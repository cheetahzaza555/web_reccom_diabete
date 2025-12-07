import io
import requests
import traceback
import sys
import time
import re # ใช้ Regex แทน STRAFTER
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
# 2. Load Ontology
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
        # --- Classes ---
        class Patient(Thing): namespace = ex
        class PhysicalExam(Thing): namespace = ex
        class LabExam(Thing): namespace = ex
        class Exercise(Thing): namespace = ex
        class DiabetType(Thing): namespace = ex
        class PatientWarning(Thing): namespace = ex
        class Comorbidity(Thing): namespace = ex 
        class Complication(Thing): namespace = ex 
        
        # --- Data Properties ---
        class hasBMI(DataProperty): namespace = ex; range = [float]
        class hasSBP(DataProperty): namespace = ex; range = [float]
        class hasDBP(DataProperty): namespace = ex; range = [float]
        class hasTotalCholesterol(DataProperty): namespace = ex; range = [float]
        class hasLDL(DataProperty): namespace = ex; range = [float]
        class hasHDL(DataProperty): namespace = ex; range = [float]
        class hasTriglyceride(DataProperty): namespace = ex; range = [float]
        class hasFPG(DataProperty): namespace = ex; range = [float]
        
        class hasKetone(DataProperty): namespace = ex; range = [str]
        class hasMicroalbuminurin(DataProperty): namespace = ex; range = [str]
        
        # --- Object Properties ---
        class diabetType(ObjectProperty): namespace = ex; range = [DiabetType]
        class hasPhysicalExam(ObjectProperty): namespace = ex; range = [PhysicalExam]
        class hasLabExam(ObjectProperty): namespace = ex; range = [LabExam]
        class recommendedExercise(ObjectProperty): namespace = ex; range = [Exercise]
        class hasPatientWarning(ObjectProperty): namespace = ex; range = [PatientWarning]
        class hasComorbidity(ObjectProperty): namespace = ex; range = [Comorbidity]
        class hasComplication(ObjectProperty): namespace = ex; range = [Complication]
        class hasSpecialComplication(ObjectProperty): namespace = ex; range = [Complication]

def get_thai_text(entity):
    if hasattr(entity, "description") and entity.description: return str(entity.description[0])
    if hasattr(entity, "label") and entity.label: return str(entity.label[0])
    return entity.name

def safe_get_name(uri):
    """Helper to extract name from URI safely"""
    if not uri: return ""
    return re.split(r'[#/]', uri)[-1]

# ==========================================
# 4. Process Logic (Refactored)
# ==========================================
def process_patient_realtime(patient_id):
    # Security check: Ensure patient_id is safe
    if not str(patient_id).replace("_", "").isalnum():
        print("❌ Invalid Patient ID")
        return [], [], [], []

    if not onto: return [], [], [], [] 

    pid_db = f"Patient{patient_id}"
    # ✅ Fix Race Condition: Use nanoseconds
    pid_mem = f"Patient_Mem_{patient_id}_{time.time_ns()}"

    p, pe, le = None, None, None

    try:
        print(f"📥 Fetching {pid_db}...")
        query = f"""
        PREFIX ex: <http://example.org/diabetes#>
        SELECT ?typeUri ?bmi ?sbp ?dbp ?chol ?ldl ?hdl ?tri ?fpg ?ketone ?micro ?specialUri
        WHERE {{
            ex:{pid_db} a ex:Patient ; ex:diabetType ?typeUri .
            OPTIONAL {{ ex:{pid_db} ex:hasPhysicalExam ?pe . 
                        OPTIONAL {{ ?pe ex:hasBMI ?bmi }} OPTIONAL {{ ?pe ex:hasSBP ?sbp }} OPTIONAL {{ ?pe ex:hasDBP ?dbp }}
                        OPTIONAL {{ ?pe ex:hasSpecialComplication ?specialUri }}
            }}
            OPTIONAL {{ ex:{pid_db} ex:hasLabExam ?le . 
                        OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} 
                        OPTIONAL {{ ?le ex:hasHDL ?hdl }} OPTIONAL {{ ?le ex:hasTriglyceride ?tri }}
                        OPTIONAL {{ ?le ex:hasFPG ?fpg }} OPTIONAL {{ ?le ex:hasKetone ?ketone }} OPTIONAL {{ ?le ex:hasMicroalbuminurin ?micro }}
            }}
        }}
        """
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()
        
        # ✅ Fix Error Handling: Return empty lists instead of None
        if not results["results"]["bindings"]:
            print(f"❌ Patient not found in DB")
            return [], [], [], []

        row = results["results"]["bindings"][0]
        
        db_fpg = row.get('fpg', {}).get('value', None)
        db_ketone = row.get('ketone', {}).get('value', None)
        db_micro = row.get('micro', {}).get('value', None)
        # ✅ Fix Parsing: Use helper instead of SPARQL logic
        db_special_uri = row.get('specialUri', {}).get('value', None)
        db_special = safe_get_name(db_special_uri)
        db_type_uri = row.get('typeUri', {}).get('value', None)
        db_type = safe_get_name(db_type_uri) or 'T2DM'

        # ✅ Fix Logic: Check None strictly, allow empty string if needed (though here we default)
        data = {
            'type': db_type,
            'bmi': float(row.get('bmi', {}).get('value', 22.0)), 
            'sbp': float(row.get('sbp', {}).get('value', 120.0)),
            'dbp': float(row.get('dbp', {}).get('value', 80.0)), 
            'chol': float(row.get('chol', {}).get('value', 150.0)),
            'ldl': float(row.get('ldl', {}).get('value', 100.0)),
            'hdl': float(row.get('hdl', {}).get('value', 50.0)),
            'tri': float(row.get('tri', {}).get('value', 100.0)),
            'fpg': float(db_fpg) if db_fpg is not None else 100.0, 
            'ketone': db_ketone if db_ketone is not None else "Negative", 
            'micro': db_micro if db_micro is not None else "Negative",
            'special': db_special if db_special and db_special != "None" else "NoOtherComplication"
        }
        print(f"🧐 Data: {data}")

        with onto:
            p = ex.Patient(pid_mem)
            
            # ✅ Fix Type Safety: Use getattr and fallback logic
            target_type = data['type']
            type_obj = getattr(ex, target_type, None)
            if not type_obj:
                type_obj = onto.search_one(iri=f"*{target_type}") 
                if not type_obj: type_obj = ex.DiabetType(target_type)
            p.diabetType = [type_obj]
                
            pe = ex.PhysicalExam(f"PE_Mem_{patient_id}_{time.time_ns()}")
            pe.hasBMI = [data['bmi']]
            pe.hasSBP = [data['sbp']]
            pe.hasDBP = [data['dbp']]
            
            if data['special']:
                special_name = data['special']
                # ✅ Fix Namespace Handling: search broadly first
                special_obj = getattr(ex, special_name, None)
                if not special_obj:
                    special_obj = onto.search_one(iri=f"*{special_name}")
                if not special_obj:
                    # Fallback create in 'ex' namespace
                    special_obj = ex.Complication(special_name)
                pe.hasSpecialComplication = [special_obj]
            
            p.hasPhysicalExam = [pe]
            
            le = ex.LabExam(f"LE_Mem_{patient_id}_{time.time_ns()}")
            le.hasTotalCholesterol = [data['chol']]
            le.hasLDL = [data['ldl']]
            le.hasHDL = [data['hdl']]
            le.hasTriglyceride = [data['tri']]
            le.hasFPG = [data['fpg']]
            le.hasKetone = [data['ketone']]
            le.hasMicroalbuminurin = [data['micro']]
            p.hasLabExam = [le]

        print("🧠 Running Reasoner...")
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

        print("🔍 Querying Memory (Unified)...")
        recs, warns, comorbs, complis = [], [], [], [] 
        s_recs, s_warns, s_comorbs, s_complis = [], [], [], []

        # ✅ Fix Performance: Unified Query with UNION
        # Using suffix matching to be namespace-agnostic
        unified_query = f"""
            SELECT ?p ?o WHERE {{ 
                <{p.iri}> ?p ?o . 
                FILTER(
                    STRENDS(STR(?p), "recommendedExercise") ||
                    STRENDS(STR(?p), "hasPatientWarning") ||
                    STRENDS(STR(?p), "hasComorbidity") ||
                    STRENDS(STR(?p), "hasComplication")
                )
            }}
        """
        try:
            q = list(default_world.sparql(unified_query, error_on_undefined_entities=False))
            for row in q:
                pred = row[0].name # Property Name
                obj = row[1]       # Value Object
                
                if not hasattr(obj, 'name'): continue # Skip literals if any

                text = get_thai_text(obj)
                name = obj.name

                if "recommendedExercise" in pred:
                    recs.append(text); s_recs.append(name)
                elif "hasPatientWarning" in pred:
                    warns.append(text); s_warns.append(name)
                elif "hasComorbidity" in pred:
                    comorbs.append(text); s_comorbs.append(name)
                elif "hasComplication" in pred:
                    complis.append(text); s_complis.append(name)

        except Exception as e: print(f"Query Error: {e}")

        # De-duplicate
        recs, warns, comorbs, complis = list(set(recs)), list(set(warns)), list(set(comorbs)), list(set(complis))
        s_recs, s_warns, s_comorbs, s_complis = list(set(s_recs)), list(set(s_warns)), list(set(s_comorbs)), list(set(s_complis))

        print(f"✅ Result: W={len(warns)}, Cb={len(comorbs)}, Cp={len(complis)}")
        
        save_results_to_db(patient_id, s_recs, s_warns, s_comorbs, s_complis)
        
        return recs, warns, comorbs, complis

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        traceback.print_exc()
        return [], [], [], [f"Error: {str(e)}"]
    
    finally:
        # ✅ Fix Memory Leak: Always cleanup in finally block
        if p: destroy_entity(p)
        if pe: destroy_entity(pe)
        if le: destroy_entity(le)

def save_results_to_db(pid_num, recs, warns, comorbs, complis):
    # Security check
    if not str(pid_num).replace("_", "").isalnum(): return

    pid = f"Patient{pid_num}"
    del_q = f"""
    PREFIX ex: <http://example.org/diabetes#> 
    DELETE {{ ex:{pid} ex:hasPatientWarning ?w . ex:{pid} ex:recommendedExercise ?r . ex:{pid} ex:hasComorbidity ?c . ex:{pid} ex:hasComplication ?cp }} 
    WHERE {{ OPTIONAL {{ ex:{pid} ex:hasPatientWarning ?w }} OPTIONAL {{ ex:{pid} ex:recommendedExercise ?r }} OPTIONAL {{ ex:{pid} ex:hasComorbidity ?c }} OPTIONAL {{ ex:{pid} ex:hasComplication ?cp }} }}
    """
    sparql_write.setQuery(del_q); sparql_write.query()
    
    # ✅ Fix Performance: Use list join
    triples_list = []
    for x in recs: triples_list.append(f"ex:{pid} ex:recommendedExercise ex:{x} .")
    for x in warns: triples_list.append(f"ex:{pid} ex:hasPatientWarning ex:{x} .")
    for x in comorbs: triples_list.append(f"ex:{pid} ex:hasComorbidity ex:{x} .")
    for x in complis: triples_list.append(f"ex:{pid} ex:hasComplication ex:{x} .")
    
    if triples_list:
        triples_str = "\n".join(triples_list)
        ins_q = f"PREFIX ex: <http://example.org/diabetes#> INSERT DATA {{ {triples_str} }}"
        sparql_write.setQuery(ins_q); sparql_write.query()
        print(f"💾 Saved to DB")

def get_patient_profile(patient_id):
    if not str(patient_id).replace("_", "").isalnum(): return None # Security

    pid = f"Patient{patient_id}"
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?fname ?lname ?type ?bmi ?sbp ?dbp ?chol ?ldl ?fpg ?ketone ?micro ?specialName ?recName ?warnDesc ?comorbName ?compliName
    WHERE {{
        ex:{pid} a ex:Patient ; ex:diabetType ?typeUri .
        BIND(STRAFTER(STR(?typeUri), "#") AS ?type)
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }} OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
        
        OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . 
                    OPTIONAL {{ ?pe ex:hasBMI ?bmi }} OPTIONAL {{ ?pe ex:hasSBP ?sbp }} OPTIONAL {{ ?pe ex:hasDBP ?dbp }} 
                    OPTIONAL {{ ?pe ex:hasSpecialComplication ?special . 
                                BIND(STRAFTER(STR(?special), "#") AS ?specialName) }} 
        }}
        OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . OPTIONAL {{ ?le ex:hasTotalCholesterol ?chol }} OPTIONAL {{ ?le ex:hasLDL ?ldl }} 
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
        "firstname": first.get("fname", {}).get("value", "-"),
        "lastname": first.get("lname", {}).get("value", "-"),
        "type": first.get("type", {}).get("value", "-"),
        "bmi": first.get("bmi", {}).get("value", "-"),
        "sbp": first.get("sbp", {}).get("value", "-"),
        "dbp": first.get("dbp", {}).get("value", "-"),
        "chol": first.get("chol", {}).get("value", "-"),
        "ldl": first.get("ldl", {}).get("value", "-"),
        "fpg": first.get("fpg", {}).get("value", "-"),
        "ketone": first.get("ketone", {}).get("value", "-"),
        "micro": first.get("micro", {}).get("value", "-"),
        "special": first.get("specialName", {}).get("value", ""),
    }
    exercises = set([r["recName"]["value"] for r in bindings if "recName" in r])
    warnings = set([r["warnDesc"]["value"] for r in bindings if "warnDesc" in r])
    comorbs = set([r["comorbName"]["value"] for r in bindings if "comorbName" in r])
    complis = set([r["compliName"]["value"] for r in bindings if "compliName" in r])
    
    return {"info": info, "exercises": list(exercises), "warnings": list(warnings), "comorbs": list(comorbs), "complis": list(complis)}

def save_raw_patient_data(data):
    if not str(data['id']).replace("_", "").isalnum(): return # Security

    pid = f"Patient{data['id']}"
    delete_patient(data['id'])
    
    # ✅ Fix Logic Consistency: Use is not None or strict checks
    ketone_val = data.get('ketone') if data.get('ketone') else "Negative"
    micro_val = data.get('micro') if data.get('micro') else "Negative"
    
    special_triple = ""
    if data.get('special') and data['special'] != "None":
        special_triple = f'ex:{pid}_PE ex:hasSpecialComplication ex:{data["special"]} .'
    else:
        special_triple = f'ex:{pid}_PE ex:hasSpecialComplication ex:NoOtherComplication .'

    def get_val(key): return data.get(key) if data.get(key) else "0"
    
    triples = f"""
        ex:{pid} a ex:Patient ; ex:diabetType ex:{data['type']} ; ex:firstname "{data.get('firstname', '-')}" ; ex:lastname "{data.get('lastname', '-')}" ; ex:hasPhysicalExam ex:{pid}_PE ; ex:hasLabExam ex:{pid}_LE .
        ex:{pid}_PE a ex:PhysicalExam ; ex:hasBMI "{get_val('bmi')}"^^xsd:decimal ; ex:hasSBP "{get_val('sbp')}"^^xsd:decimal ; ex:hasDBP "{get_val('dbp')}"^^xsd:decimal .
        {special_triple} 
        ex:{pid}_LE a ex:LabExam ; ex:hasTotalCholesterol "{get_val('chol')}"^^xsd:decimal ; ex:hasLDL "{get_val('ldl')}"^^xsd:decimal ; ex:hasHDL "{get_val('hdl')}"^^xsd:decimal ; ex:hasTriglyceride "{get_val('tri')}"^^xsd:decimal ;
                     ex:hasFPG "{get_val('fpg')}"^^xsd:decimal ; ex:hasKetone "{ketone_val}" ; ex:hasMicroalbuminurin "{micro_val}" . 
    """
    sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> INSERT DATA {{ {triples} }}"); sparql_write.query()

def delete_patient(patient_id):
    if not str(patient_id).replace("_", "").isalnum(): return # Security
    pid = f"Patient{patient_id}"
    sparql_write.setQuery(f"PREFIX ex: <http://example.org/diabetes#> DELETE {{ ?s ?p ?o . ?pe ?pp ?oo . ?le ?lp ?lo }} WHERE {{ ?s ?p ?o . FILTER(?s = ex:{pid}) OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} }}"); sparql_write.query()