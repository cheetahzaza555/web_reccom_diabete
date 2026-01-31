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
        # 1. เตรียมตัวแปร
        data = {}
        target_specials = []
        target_favorites = [] 

        if input_data:
            print(f"⚡ Processing {patient_id} (Direct)...")
            
            # 🔥🔥 [จุดที่แก้] แปลง String เป็น Float ให้หมดตรงนี้ครับ 🔥🔥
            data = {
                'type': input_data.get('type', 'T2DM'),
                'weight': safe_float(input_data.get('weight')),
                'height': safe_float(input_data.get('height')),
                'bmi': safe_float(input_data.get('bmi')),
                'sbp': safe_float(input_data.get('sbp')),
                'dbp': safe_float(input_data.get('dbp')),
                'chol': safe_float(input_data.get('chol')),
                'ldl': safe_float(input_data.get('ldl')),
                'hdl': safe_float(input_data.get('hdl')),
                'tri': safe_float(input_data.get('tri')),
                'fpg': safe_float(input_data.get('fpg')),
                'ketone': input_data.get('ketone', 'Negative'),
                'micro': input_data.get('micro', 'Negative'),
                'frequency': input_data.get('frequency')
            }
            
            raw_sp = input_data.get('special')
            if isinstance(raw_sp, list): target_specials = raw_sp
            elif isinstance(raw_sp, str) and raw_sp != "None": target_specials = [raw_sp]
            
            target_favorites = input_data.get('favorites', [])
        
        else:
            print(f"📥 Fetching {patient_id} from DB...")
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
                'frequency': safe_get_name(freq_uri)
            }

        # คำนวณ BMI ถ้าไม่มีมาให้
        if data['bmi'] is None and data['weight'] and data['height']:
            try: data['bmi'] = round(data['weight'] / ((data['height']/100)**2), 2)
            except: pass
        if data['fpg'] is None: data['fpg'] = 100.0

        print(f"🧐 Analyzed: {data}")

        # 2. สร้าง Instance ใน Memory
        with onto:
            p = ex.Patient(pid_mem)
            t_obj = onto.search_one(iri=f"*{data['type']}") or ex.DiabetType(data['type'])
            p.diabetType = [t_obj] 
            
            if data.get('frequency'):
                freq_obj = onto.search_one(iri=f"*{data['frequency']}")
                if freq_obj: p.exerciseFrequency = [freq_obj]

            pe = ex.PhysicalExam(f"PE_{unique_suffix}")
            if data.get('weight'): pe.hasWeight = [data['weight']]
            if data.get('height'): pe.hasHeight = [data['height']]
            if data.get('bmi'): pe.hasBMI = [data['bmi']]
            if data.get('sbp'): pe.hasSBP = [data['sbp']]
            if data.get('dbp'): pe.hasDBP = [data['dbp']]
            
            pe.hasSpecialComplication = [] 
            for sp in target_specials:
                sp_obj = onto.search_one(iri=f"*{sp}") or ex.Complication(sp)
                pe.hasSpecialComplication.append(sp_obj)
            p.hasPhysicalExam = [pe]
            
            le = ex.LabExam(f"LE_{unique_suffix}")
            if data.get('chol'): le.hasTotalCholesterol = [data['chol']]
            if data.get('ldl'): le.hasLDL = [data['ldl']]
            if data.get('hdl'): le.hasHDL = [data['hdl']]
            if data.get('tri'): le.hasTriglyceride = [data['tri']]
            if data.get('fpg'): le.hasFPG = [data['fpg']]
            le.hasKetone = [data.get('ketone')]
            le.hasMicroalbuminurin = [data.get('micro')]
            p.hasLabExam = [le]

            p.favoriteExercise = []
            for f in target_favorites:
                f_obj = onto.search_one(iri=f"*{f}")
                if not f_obj: 
                    print(f"⚠️ Warning: Exercise '{f}' not found in Ontology! Creating temp instance.")
                    f_obj = ex.Exercise(f)
                p.favoriteExercise.append(f_obj)

        print("🧠 Running Reasoner...")
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        
        print("🔍 Extracting Results...")
        recs, warns, comorbs, complis = [], [], [], [] 
        s_recs, s_warns, s_comorbs, s_complis = [], [], [], []
        s_avoids, s_intens, s_freqs = [], [], []

        # 1. Exercises
        recs_list = list(p.recommendedExercise)
        
        if not recs_list and target_favorites:
            avoid = [val.name for val in getattr(p, "avoidExercise", [])]
            for f in p.favoriteExercise:
                if f.name not in avoid: recs_list.append(f)

        print("🔍 Extracting Results...")
        recs, warns, comorbs, complis = [], [], [], [] 
        s_recs, s_warns, s_comorbs, s_complis = [], [], [], []
        s_avoids, s_intens, s_freqs = [], [], []

        # 1. Exercises
        recs_list = list(p.recommendedExercise)
        
        # 🔥 [แก้ใหม่] เอา Favorite Exercise มาใส่ด้วยเสมอ (ถ้าไม่ติด Avoid)
        # ไม่ต้องรอให้ recs_list ว่างเปล่า
        if target_favorites:
            # ดึงรายชื่อท่าที่ต้องห้ามออกมาเช็ค
            avoid_names = [val.name for val in getattr(p, "avoidExercise", [])]
            
            for f in p.favoriteExercise:
                # ถ้าสิ่งที่ชอบ ไม่ได้อยู่ในรายการห้าม -> ให้แนะนำได้เลย!
                if f.name not in avoid_names: 
                    recs_list.append(f)

        # วนลูปสร้าง Text เพื่อแสดงผล
        for r in list(set(recs_list)):
            s_recs.append(r.name) # เก็บชื่อท่าลง DB
            name = get_thai_text(r)
            
            details = []
            try:
                # พยายามดึงความหนัก/ความถี่ (ถ้า Reasoner ให้มา)
                ints = getattr(r, "intensityOfExercise", [])
                if not isinstance(ints, list): ints = [ints]
                for i in ints:
                    txt = get_thai_text(i) if hasattr(i, 'label') or hasattr(i, 'name') else str(i)
                    details.append(f"ความหนัก: {txt}")
                
                freqs = getattr(r, "exerciseFrequency", [])
                if not isinstance(freqs, list): freqs = [freqs]
                for f in freqs:
                    txt = get_thai_text(f) if hasattr(f, 'label') or hasattr(f, 'name') else str(f)
                    details.append(f"ความถี่: {txt}")
            except: pass
            
            # ถ้าเป็น Favorite ล้วนๆ อาจจะไม่มี details ติดมา ก็ให้แสดงแค่ชื่อ
            if details: recs.append(f"{name} ({', '.join(details)})")
            else: recs.append(name)

        # 2. Warnings / Comorbs / Complis
        for w in p.hasPatientWarning: 
            warns.append(get_thai_text(w)); s_warns.append(w.name)
        for c in p.hasComorbidity: 
            comorbs.append(get_thai_text(c)); s_comorbs.append(c.name)
        for cp in p.hasComplication: 
            complis.append(get_thai_text(cp)); s_complis.append(cp.name)

        # 3. Collect Extra Data
        for a in getattr(p, "avoidExercise", []): s_avoids.append(a.name)
        for i in getattr(p, "intensityOfExercise", []): s_intens.append(i.name)
        for f in getattr(p, "exerciseFrequency", []): s_freqs.append(f.name)

        recs = list(set(recs)); warns = list(set(warns))
        comorbs = list(set(comorbs)); complis = list(set(complis))

        print(f"✅ Result: Ex={len(recs)}, W={len(warns)}, Avoid={len(s_avoids)}")
        
        # ส่งค่าให้ครบ 8 ตัว
        save_results_to_db(
            patient_id, 
            list(set(s_recs)), 
            list(set(s_warns)), 
            list(set(s_comorbs)), 
            list(set(s_complis)), 
            list(set(s_avoids)), 
            list(set(s_intens)), 
            list(set(s_freqs))
        )
        return recs, warns, comorbs, complis

    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return [], [], [], [f"Error: {str(e)}"]
    finally:
        if p: 
            try: destroy_entity(p)
            except: pass