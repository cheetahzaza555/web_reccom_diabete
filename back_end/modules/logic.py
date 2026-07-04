# modules/logic.py
import uuid
import traceback
from owlready2 import *
from modules.db import (
    validate_id,
    sparql_read,
    safe_get_name,
    safe_float,
    get_thai_text,
    save_results_to_db
)
from modules.ontology import onto, ex


def process_patient_realtime(patient_id, input_data=None):
    if not validate_id(patient_id) or not onto:
        return [], [], [], []

    # ตัดคำว่า Patient ออกก่อน (กันเหนียว)
    clean_id = str(patient_id).replace("Patient", "")
    unique_suffix = uuid.uuid4().hex[:8]
    pid_mem = f"Patient_Mem_{clean_id}_{unique_suffix}"

    # ✅ ประกาศตัวแปรทั้งหมดที่อาจถูกสร้างใน onto ไว้ล่วงหน้า
    # เพื่อให้ finally block ลบทิ้งได้ครบ ไม่เหลือค้างใน memory
    p = None
    pe = None
    le = None
    created_temp_entities = []  # เก็บ entity ใหม่ที่สร้างชั่วคราว (t_obj/sp_obj/f_obj ที่หาไม่เจอใน ontology)

    try:
        # 1. เตรียมตัวแปร
        data = {}
        target_specials = []
        target_favorites = []

        if input_data:  # มีข้อมูลส่งเข้ามาแบบตรงๆ
            print(f"⚡ Processing {patient_id} (Direct)...")

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
            if isinstance(raw_sp, list):
                target_specials = raw_sp
            elif isinstance(raw_sp, str) and raw_sp != "None":
                target_specials = [raw_sp]

            target_favorites = input_data.get('favorites', [])

        else:  # ดึงข้อมูลจาก DB ตามปกติ
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
            if not results["results"]["bindings"]:
                return [], [], [], []

            for r in results["results"]["bindings"]:
                s_uri = r.get('specialUri', {}).get('value')
                if s_uri:
                    s_name = safe_get_name(s_uri)
                    if s_name not in target_specials:
                        target_specials.append(s_name)

                f_name = r.get('favName', {}).get('value')
                if f_name and f_name not in target_favorites:
                    target_favorites.append(f_name)

            if not target_specials:
                target_specials.append("NoOtherComplication")
            row = results["results"]["bindings"][0]

            freq_uri = row.get('freqUri', {}).get('value')

            # ✅ แปลง sbp/dbp อย่างปลอดภัย ป้องกัน TypeError เมื่อไม่มีข้อมูล
            # (int(None) จะ crash ทั้งฟังก์ชันทันที ทำให้ error ไปโผล่ตรง except ข้างล่างแทน)
            sbp_val = safe_float(row.get('sbp', {}).get('value'))
            dbp_val = safe_float(row.get('dbp', {}).get('value'))

            data = {
                'type': safe_get_name(row.get('typeUri', {}).get('value')) or 'T2DM',
                'weight': safe_float(row.get('weight', {}).get('value')),
                'height': safe_float(row.get('height', {}).get('value')),
                'bmi': safe_float(row.get('bmi', {}).get('value')),
                'sbp': int(sbp_val) if sbp_val is not None else None,
                'dbp': int(dbp_val) if dbp_val is not None else None,
                'chol': safe_float(row.get('chol', {}).get('value')),
                'ldl': safe_float(row.get('ldl', {}).get('value')),
                'hdl': safe_float(row.get('hdl', {}).get('value')),
                'tri': safe_float(row.get('tri', {}).get('value')),
                'fpg': safe_float(row.get('fpg', {}).get('value')),
                'ketone': row.get('ketone', {}).get('value') or "Negative",
                'micro': row.get('micro', {}).get('value') or "Negative",
                'frequency': safe_get_name(freq_uri)
            }

        if data['bmi'] is None and data['weight'] and data['height']:
            try:
                data['bmi'] = round(data['weight'] / ((data['height'] / 100) ** 2), 2)
            except Exception as e:
                print(f"⚠️ Could not calculate BMI: {e}")

        print(f"🧐 Analyzed: {data}")

        # 2. สร้าง Instance ใน Memory
        with onto:
            p = ex.Patient(pid_mem)

            t_obj = onto.search_one(iri=f"*{data['type']}")
            if not t_obj:
                t_obj = ex.DiabetType(data['type'])
                created_temp_entities.append(t_obj)
            p.diabetType = [t_obj]

            if data.get('frequency'):
                freq_obj = onto.search_one(iri=f"*{data['frequency']}")
                if freq_obj:
                    p.exerciseFrequency = [freq_obj]

            pe = ex.PhysicalExam(f"PE_{unique_suffix}")
            if data.get('weight'):
                pe.hasWeight = [data['weight']]
            if data.get('height'):
                pe.hasHeight = [data['height']]
            if data.get('bmi'):
                pe.hasBMI = [data['bmi']]
            if data.get('sbp'):
                pe.hasSBP = [data['sbp']]
            if data.get('dbp'):
                pe.hasDBP = [data['dbp']]

            pe.hasSpecialComplication = []
            for sp in target_specials:
                sp_obj = onto.search_one(iri=f"*{sp}")
                if not sp_obj:
                    sp_obj = ex.Complication(sp)
                    created_temp_entities.append(sp_obj)
                pe.hasSpecialComplication.append(sp_obj)
            p.hasPhysicalExam = [pe]

            le = ex.LabExam(f"LE_{unique_suffix}")
            if data.get('chol'):
                le.hasTotalCholesterol = [data['chol']]
            if data.get('ldl'):
                le.hasLDL = [data['ldl']]
            if data.get('hdl'):
                le.hasHDL = [data['hdl']]
            if data.get('tri'):
                le.hasTriglyceride = [data['tri']]
            if data.get('fpg'):
                le.hasFPG = [data['fpg']]
            le.hasKetone = [data.get('ketone')]
            le.hasMicroalbuminurin = [data.get('micro')]
            p.hasLabExam = [le]

            p.favoriteExercise = []
            for f in target_favorites:
                f_obj = onto.search_one(iri=f"*{f}")
                if not f_obj:
                    print(f"⚠️ Warning: Exercise '{f}' not found in Ontology! Creating temp instance.")
                    f_obj = ex.Exercise(f)
                    created_temp_entities.append(f_obj)
                p.favoriteExercise.append(f_obj)

        print("🧠 Running Reasoner...")
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

        print("🔍 Extracting Results...")
        recs, warns, comorbs, complis = [], [], [], []
        s_recs, s_warns, s_comorbs, s_complis = [], [], [], []
        s_avoids, s_intens, s_freqs = [], [], []

        # 1. Exercises
        recs_list = list(p.recommendedExercise)

        for r in list(set(recs_list)):
            s_recs.append(r.name)  # เก็บชื่อท่าลง DB
            name = get_thai_text(r)

            details = []
            try:
                ints = getattr(r, "intensityOfExercise", [])
                if not isinstance(ints, list):
                    ints = [ints]
                for i in ints:
                    txt = get_thai_text(i) if hasattr(i, 'label') or hasattr(i, 'name') else str(i)
                    details.append(f"ความหนัก: {txt}")

                freqs = getattr(r, "exerciseFrequency", [])
                if not isinstance(freqs, list):
                    freqs = [freqs]
                for f in freqs:
                    txt = get_thai_text(f) if hasattr(f, 'label') or hasattr(f, 'name') else str(f)
                    details.append(f"ความถี่: {txt}")
            except Exception as e:
                # ✅ log ไว้แทนการเงียบสนิท จะได้รู้ว่าทำไมบางท่าไม่มีรายละเอียดความหนัก/ความถี่
                print(f"⚠️ Could not extract intensity/frequency for '{r.name}': {e}")

            final_label = f"{name} ({', '.join(details)})" if details else name

            ex_types = []
            for c in getattr(r, "is_a", []):
                if hasattr(c, "name"):
                    ex_types.append(c.name)
            type_str = ",".join(ex_types)

            recs.append({
                "label": final_label,
                "type": type_str
            })

        # 2. Warnings / Comorbs / Complis
        for w in p.hasPatientWarning:
            warns.append(get_thai_text(w))
            s_warns.append(w.name)
        for c in p.hasComorbidity:
            comorbs.append(get_thai_text(c))
            s_comorbs.append(c.name)
        for cp in p.hasComplication:
            complis.append(get_thai_text(cp))
            s_complis.append(cp.name)

        # 3. Collect Extra Data
        for a in getattr(p, "avoidExercise", []):
            s_avoids.append(a.name)
        for i in getattr(p, "intensityOfExercise", []):
            s_intens.append(i.name)
        for f in getattr(p, "exerciseFrequency", []):
            s_freqs.append(f.name)

        warns = list(set(warns))
        comorbs = list(set(comorbs))
        complis = list(set(complis))

        print(f"✅ Result: Ex={len(recs)}, W={len(warns)}, Avoid={len(s_avoids)}")

        # บันทึกผลลัพธ์ลง GraphDB แบบถาวร (นี่คือจุดที่ข้อมูลถูก "บันทึก" จริงๆ)
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
        # ✅ ลบ entity ชั่วคราวทั้งหมดออกจาก onto (in-memory) หลังใช้งานเสร็จ
        # ป้องกันไม่ให้ ontology ใน RAM บวมขึ้นเรื่อยๆ ทุกครั้งที่มีการเรียกฟังก์ชันนี้
        # (ข้อมูลที่ต้องการเก็บถาวรถูกบันทึกไปยัง GraphDB แล้วผ่าน save_results_to_db ด้านบน)
        for entity in [p, pe, le] + created_temp_entities:
            if entity:
                try:
                    destroy_entity(entity)
                except Exception as e:
                    print(f"⚠️ Could not destroy temp entity '{entity}': {e}")