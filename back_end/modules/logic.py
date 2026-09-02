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


def _classify_special(entity):
    """
    ✅ [FIX] Helper สำหรับแยกว่า entity ที่ได้มาจาก target_specials
    ควรจัดเป็น 'comorbidity' (โรคร่วม) หรือ 'complication' (ภาวะแทรกซ้อน)
    โดยเช็คจาก class hierarchy ของมันใน ontology (ex.Comorbidity)

    หมายเหตุ: ปรับ logic ตรงนี้ให้ตรงกับ schema จริงของคุณอีกทีถ้าจำเป็น
    (เช่นถ้า ontology ใช้ชื่อคลาสอื่นแทน ex.Comorbidity)
    """
    comorbidity_cls = getattr(ex, "Comorbidity", None)
    if comorbidity_cls is None or entity is None:
        return "complication"

    try:
        all_types = set(entity.is_a)
        for t in list(all_types):
            if hasattr(t, "ancestors"):
                all_types |= set(t.ancestors())
        if comorbidity_cls in all_types:
            return "comorbidity"
    except Exception:
        pass

    return "complication"


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

            # ✅ [FIX] hasSBP / hasDBP ใน ontology ประกาศ range เป็น xsd:positiveInteger
            # (ดูตัวอย่างผู้ป่วยที่ข้อมูลถูกต้อง: "115"^^xsd:positiveInteger)
            # เดิม branch นี้ใช้ safe_float() ทำให้ได้ float (เช่น 113.0) ซึ่ง
            # owlready2 จะ serialize เป็น xsd:double ไม่ตรงกับ range ที่ประกาศไว้
            # ทำให้ builtin comparison ในกฎ SWRL ที่เช็ค SBP/DBP (เช่น Rule 15/19)
            # ไม่ match แม้ค่าจะอยู่ในช่วงที่ถูกต้องก็ตาม -> ต้อง cast เป็น int
            # เหมือนที่ branch "ดึงจาก DB" ทำไว้อยู่แล้วด้านล่าง
            sbp_val = safe_float(input_data.get('sbp'))
            dbp_val = safe_float(input_data.get('dbp'))

            data = {
                'type': input_data.get('type', 'T2DM'),
                'weight': safe_float(input_data.get('weight')),
                'height': safe_float(input_data.get('height')),
                'bmi': safe_float(input_data.get('bmi')),
                'sbp': int(sbp_val) if sbp_val is not None else None,
                'dbp': int(dbp_val) if dbp_val is not None else None,
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

            # ✅ [FIX] เดิมโค้ดใส่ target_specials ลงใน pe.hasSpecialComplication
            # (domain = PhysicalExam) เท่านั้น แต่กฎ SWRL ส่วนใหญ่ (88 จุดของ
            # hasComplication + 60 จุดของ hasComorbidity จากทั้งหมด 62 กฎ) เช็ค
            # ex:hasComplication / ex:hasComorbidity บนตัว Patient (x) โดยตรง
            # ทำให้ Patient ที่สร้างขึ้นไม่มี complication/comorbidity ติดตัวเลย
            # และแทบทุกกฎ unify ไม่ได้ -> ไม่มีกฎไหน fire
            #
            # ด้านล่างนี้จึงแยก target_specials ไปใส่ทั้ง p.hasComplication /
            # p.hasComorbidity (ตาม class ของแต่ละ entity) และยังคงใส่ลง
            # pe.hasSpecialComplication ไว้ด้วย เผื่อ 6 กฎที่อ้างอิง property นี้
            # โดยเฉพาะยังทำงานตามเดิม
            sp_objs = []
            for sp in target_specials:
                sp_obj = onto.search_one(iri=f"*{sp}")
                if not sp_obj:
                    sp_obj = ex.Complication(sp)
                    created_temp_entities.append(sp_obj)
                sp_objs.append(sp_obj)

            p.hasComplication = []
            p.hasComorbidity = []
            for sp_obj in sp_objs:
                if _classify_special(sp_obj) == "comorbidity":
                    p.hasComorbidity.append(sp_obj)
                else:
                    p.hasComplication.append(sp_obj)

            # ถ้าไม่มีค่าเลย ให้ fallback เป็นค่า "ไม่มี" ตาม pattern ที่ใช้ใน
            # ontology จริง (ดูตัวอย่างผู้ป่วยที่ข้อมูลครบ) กันไม่ให้ hasComplication /
            # hasComorbidity ว่างเปล่าจนกฎที่เช็คเงื่อนไข "ไม่มีภาวะแทรกซ้อน" พังไปด้วย
            if not p.hasComplication:
                default_comp = (onto.search_one(iri="*NoGeneralComplication")
                                 or onto.search_one(iri="*NoOtherComplication"))
                if default_comp:
                    p.hasComplication.append(default_comp)
            if not p.hasComorbidity:
                default_comorb = onto.search_one(iri="*NoComorbidity")
                if default_comorb:
                    p.hasComorbidity.append(default_comorb)

            pe.hasSpecialComplication = list(sp_objs)
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

        # ✅ [DEBUG] เช็คค่าบน pe / le ตรงๆ ก่อนรัน reasoner (ไม่ผ่าน p)
        # เพื่อยืนยันว่าค่าที่ควรจะอยู่บน PhysicalExam/LabExam จริงๆ landed
        # ถูกจุดหรือไม่ ก่อนที่ Pellet จะเอาไปประมวลผลกฎ 15/16/19/20
        print("🧪 [DEBUG-PRE] pe.hasWeight:", pe.hasWeight, " hasHeight:", pe.hasHeight,
              " hasBMI:", pe.hasBMI, " hasSBP:", pe.hasSBP, " hasDBP:", pe.hasDBP)
        print("🧪 [DEBUG-PRE] pe.hasSpecialComplication:",
              [x.name for x in pe.hasSpecialComplication])
        print("🧪 [DEBUG-PRE] le.hasFPG:", le.hasFPG, " hasTotalCholesterol:", le.hasTotalCholesterol,
              " hasLDL:", le.hasLDL, " hasHDL:", le.hasHDL, " hasTriglyceride:", le.hasTriglyceride)
        print("🧪 [DEBUG-PRE] le.hasKetone:", le.hasKetone, " hasMicroalbuminurin:", le.hasMicroalbuminurin)
        print("🧪 [DEBUG-PRE] p.hasPhysicalExam:", getattr(p, 'hasPhysicalExam', None),
              " p.hasLabExam:", getattr(p, 'hasLabExam', None))

        print("🧠 Running Reasoner...")
        # พิมพ์ดูว่า Owlready2 ถือ SWRL Rule อยู่ในมือจริงๆ กี่ข้อ
        print("📌 Real Rules in Owlready2 Memory:", len(list(onto.rules())))
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

        # ✅ [DEBUG] พิมพ์ state ของ patient หลัง reasoner รันเสร็จ เพื่อเช็คว่า
        # precondition ของกฎแต่ละข้อ (hasComplication/hasComorbidity/diabetType/
        # favoriteExercise) ถูก assert/infer ถูกต้องหรือไม่ ก่อนจะไป extract ผลลัพธ์
        print("🩺 [DEBUG] diabetType:", [t.name for t in getattr(p, 'diabetType', [])])
        print("🩺 [DEBUG] hasComplication:", [c.name for c in getattr(p, 'hasComplication', [])])
        print("🩺 [DEBUG] hasComorbidity:", [c.name for c in getattr(p, 'hasComorbidity', [])])
        print("🩺 [DEBUG] favoriteExercise:", [f.name for f in getattr(p, 'favoriteExercise', [])])
        print("🩺 [DEBUG] hasPatientWarning:", [w.name for w in getattr(p, 'hasPatientWarning', [])])

        print("🔍 Extracting Results...")
        recs, warns, comorbs, complis = [], [], [], []
        s_recs, s_warns, s_comorbs, s_complis = [], [], [], []
        s_avoids, s_intens, s_freqs = [], [], []

        # ----------------------------------------------------
        # 0. ดึงข้อมูล Avoid, Intensity, Frequency ออกมาก่อน
        # ----------------------------------------------------
        for a in getattr(p, "avoidExercise", []):
            s_avoids.append(a.name)
        for i in getattr(p, "intensityOfExercise", []):
            s_intens.append(i.name)
        for f in getattr(p, "exerciseFrequency", []):
            s_freqs.append(f.name)

        # เช็กว่ามีคำสั่งห้ามออกกำลังกายเด็ดขาดหรือไม่ (เช่น Avoid4)
        has_strict_avoid = "Avoid4" in s_avoids or "Avoid12" in s_avoids

        # ----------------------------------------------------
        # 1. Exercises (ทำงานเฉพาะเมื่อไม่มีคำสั่งห้ามเด็ดขาด)
        # ----------------------------------------------------
        if has_strict_avoid:
            print(f"🛑 [FILTER] Patient {p.name} has Avoid condition ({s_avoids})! Clearing recommended exercises.")
            recs = []
            s_recs = []
        else:
            recs_list = list(getattr(p, "recommendedExercise", []))

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

        # ----------------------------------------------------
        # 2. Warnings / Comorbs / Complis (ทำงานตามปกติ)
        # ----------------------------------------------------
        for w in p.hasPatientWarning:
            warns.append(get_thai_text(w))
            s_warns.append(w.name)
        for c in p.hasComorbidity:
            comorbs.append(get_thai_text(c))
            s_comorbs.append(c.name)
        for cp in p.hasComplication:
            complis.append(get_thai_text(cp))
            s_complis.append(cp.name)

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