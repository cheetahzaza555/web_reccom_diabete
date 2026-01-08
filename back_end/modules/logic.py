# modules/logic.py
import uuid
import traceback
from owlready2 import *
from modules.database import (
    validate_id, 
    sparql_read, 
    safe_get_name, 
    safe_float, 
    get_thai_text,
    save_results_to_db
)
from modules.ontology import onto, ex

def process_patient_realtime(patient_id, input_data=None):
    if not validate_id(patient_id) or not onto: return [], [], [], []

    unique_suffix = uuid.uuid4().hex[:8]
    pid_mem = f"Patient_Mem_{patient_id}_{unique_suffix}"
    p = None

    try:
        # 1. เตรียม Data
        data, target_specials, target_favorites = {}, [], []
        
        if input_data:
            print(f"⚡ Processing {patient_id} (Direct)...")
            data = input_data
            data['frequency'] = input_data.get('frequency') # รับค่าความถี่
            
            raw_sp = input_data.get('special')
            if isinstance(raw_sp, list): target_specials = raw_sp
            elif isinstance(raw_sp, str) and raw_sp != "None": target_specials = [raw_sp]
            target_favorites = input_data.get('favorites', [])
        else:
            print(f"📥 Fetching {patient_id} from DB...")
            # Query ดึงข้อมูลจาก DB (รวมถึง Frequency)
            query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            SELECT ?typeUri ?weight ?height ?bmi ?sbp ?dbp ?chol ?ldl ?hdl ?tri ?fpg ?ketone ?micro ?specialUri ?favName ?freqUri
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
                OPTIONAL {{ ex:Patient{patient_id} ex:exerciseFrequency ?freqUri }}
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
                f_name = r.get('favName', {}).get('value')
                if f_name and f_name not in target_favorites: target_favorites.append(f_name)
            
            if not target_specials: target_specials.append("NoOtherComplication")
            row = results["results"]["bindings"][0]
            
            # ดึงค่า Frequency
            freq_uri = row.get('freqUri', {}).get('value')
            
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
                'frequency': safe_get_name(freq_uri) # เก็บค่า Frequency
            }

        if data['bmi'] is None and data['weight'] and data['height']:
            try: data['bmi'] = round(data['weight'] / ((data['height']/100)**2), 2)
            except: pass
        if data['fpg'] is None: data['fpg'] = 100.0

        print(f"🧐 Analyzed: {data}")

        # 2. สร้าง Instance ใน Ontology (Memory)
        with onto:
            p = ex.Patient(pid_mem)
            t_obj = onto.search_one(iri=f"*{data['type']}") or ex.DiabetType(data['type'])
            p.diabetType = [t_obj]
            
            # ใส่ Frequency ให้ Reasoner รู้จัก
            if data.get('frequency'):
                freq_obj = onto.search_one(iri=f"*{data['frequency']}")
                if freq_obj: p.exerciseFrequency = [freq_obj]

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
                f_obj = onto.search_one(iri=f"*{f}") or ex.Exercise(f)
                p.favoriteExercise.append(f_obj)

        print("🧠 Running Reasoner...")
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        
        print("🔍 Extracting Results...")
        recs, warns, comorbs, complis = [], [], [], [] 
        s_recs, s_warns, s_comorbs, s_complis = [], [], [], []
        s_avoids, s_intens, s_freqs = [], [], []

        for prop in p.get_properties():
            values = prop[p]
            prop_iri = prop.iri
            
            if prop_iri.endswith("recommendedExercise"):
                for val in values:
                    if hasattr(val, 'name'):
                        s_recs.append(val.name)
                        ex_name = get_thai_text(val)
                        details = []
                        try:
                            # ดึง Intensity จากตัวคนไข้ (p) ก่อน
                            ints = getattr(p, "intensityOfExercise", [])
                            if not ints: ints = getattr(val, "intensityOfExercise", [])
                            if not isinstance(ints, list): ints = [ints]
                            for i in ints:
                                txt = get_thai_text(i) if hasattr(i, 'label') or hasattr(i, 'name') else str(i)
                                details.append(f"ความหนัก: {txt}")

                            # ดึง Frequency จากตัวคนไข้ (p) ก่อน
                            freqs = getattr(p, "exerciseFrequency", [])
                            if not freqs: freqs = getattr(val, "exerciseFrequency", [])
                            if not isinstance(freqs, list): freqs = [freqs]
                            for f in freqs:
                                txt = get_thai_text(f) if hasattr(f, 'label') or hasattr(f, 'name') else str(f)
                                details.append(f"ความถี่: {txt}")
                        except: pass
                        
                        if details: recs.append(f"{ex_name} ({', '.join(details)})")
                        else: recs.append(ex_name)
            
            elif prop_iri.endswith("avoidExercise"):
                for val in values:
                    if hasattr(val, 'name'): s_avoids.append(val.name)
            elif prop_iri.endswith("intensityOfExercise"):
                for val in values:
                    if hasattr(val, 'name'): s_intens.append(val.name)
            elif prop_iri.endswith("exerciseFrequency"):
                for val in values:
                    if hasattr(val, 'name'): s_freqs.append(val.name)
            elif prop_iri.endswith("hasPatientWarning"):
                for val in values:
                    if hasattr(val, 'name'): 
                        warns.append(get_thai_text(val))
                        s_warns.append(val.name)
            elif prop_iri.endswith("hasComorbidity"):
                for val in values:
                    if hasattr(val, 'name'): 
                        comorbs.append(get_thai_text(val))
                        s_comorbs.append(val.name)
            elif prop_iri.endswith("hasComplication"):
                for val in values:
                    if hasattr(val, 'name'): 
                        complis.append(get_thai_text(val))
                        s_complis.append(val.name)

        # Clean duplicates
        recs = list(set(recs)); warns = list(set(warns))
        comorbs = list(set(comorbs)); complis = list(set(complis))
        
        # Clean URIs for saving
        s_recs = list(set(s_recs)); s_warns = list(set(s_warns))
        s_comorbs = list(set(s_comorbs)); s_complis = list(set(s_complis))
        s_avoids = list(set(s_avoids)); s_intens = list(set(s_intens)); s_freqs = list(set(s_freqs))

        print(f"✅ Result: Ex={len(recs)}, Avoid={len(s_avoids)}")
        
        # บันทึกผลลัพธ์
        save_results_to_db(patient_id, s_recs, s_warns, s_comorbs, s_complis, s_avoids, s_intens, s_freqs)
        
        return recs, warns, comorbs, complis

    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return [], [], [], [f"Error: {str(e)}"]
    finally:
        if p: destroy_entity(p)