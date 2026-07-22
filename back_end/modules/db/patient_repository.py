# modules/db/patient_repository.py
"""
ฟังก์ชันจัดการข้อมูลผู้ป่วย: บันทึกข้อมูลดิบ, ผลการแนะนำ, โปรไฟล์ผู้ป่วย
"""

from datetime import date, datetime
import uuid
from .connection import (
    sparql_read, sparql_write,
    validate_id, escape_sparql, safe_float
)


def save_raw_patient_data(data):
    if not validate_id(data.get('id')):
        return

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
            if fav:
                fav_triples += f"ex:{pid} ex:favoriteExercise ex:{escape_sparql(fav)} .\n"

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

        sparql_write.setQuery(
            f"PREFIX ex: <http://example.org/diabetes#> PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> INSERT DATA {{ {triples} }}"
        )
        sparql_write.query()
        print(f"💾 Saved Raw Data for {pid}")

    except Exception as e:
        print(f"❌ Error saving raw data: {e}")


def save_results_to_db(pid_num, recs, warns, comorbs, complis, avoids, intens, freqs):
    if not validate_id(pid_num):
        return
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
    sparql_write.setQuery(del_q)
    sparql_write.query()

    triples = []
    for x in recs:
        triples.append(f"ex:{pid} ex:recommendedExercise ex:{x} .")
    for x in warns:
        triples.append(f"ex:{pid} ex:hasPatientWarning ex:{x} .")
    for x in comorbs:
        triples.append(f"ex:{pid} ex:hasComorbidity ex:{x} .")
    for x in complis:
        triples.append(f"ex:{pid} ex:hasComplication ex:{x} .")

    for x in avoids:
        triples.append(f"ex:{pid} ex:avoidExercise ex:{x} .")
    for x in intens:
        triples.append(f"ex:{pid} ex:intensityOfExercise ex:{x} .")
    for x in freqs:
        triples.append(f"ex:{pid} ex:exerciseFrequency ex:{x} .")

    if triples:
        ins_q = f"PREFIX ex: <http://example.org/diabetes#> INSERT DATA {{ {' '.join(triples)} }}"
        sparql_write.setQuery(ins_q)
        sparql_write.query()
        print(f"💾 Saved {len(triples)} results")


def delete_patient(patient_id):
    if not validate_id(patient_id):
        return
    pid = f"Patient{patient_id}"
    sparql_write.setQuery(
        f"PREFIX ex: <http://example.org/diabetes#> "
        f"DELETE {{ ?s ?p ?o . ?pe ?pp ?oo . ?le ?lp ?lo }} "
        f"WHERE {{ ?s ?p ?o . FILTER(?s = ex:{pid}) "
        f"OPTIONAL {{ ex:{pid} ex:hasPhysicalExam ?pe . ?pe ?pp ?oo }} "
        f"OPTIONAL {{ ex:{pid} ex:hasLabExam ?le . ?le ?lp ?lo }} }}"
    )
    sparql_write.query()


def get_patient_profile(patient_id):
    if not validate_id(patient_id):
        return None
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
    if not bindings:
        return None

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
            if name not in ex_dict:
                ex_dict[name] = {"int": set(), "freq": set()}
            if "recInten" in r:
                ex_dict[name]["int"].add(r["recInten"]["value"])
            if "recFreq" in r:
                ex_dict[name]["freq"].add(r["recFreq"]["value"])

    final_exercises = []
    for name, det in ex_dict.items():
        info_parts = []
        if det["int"]:
            info_parts.append(f"ความหนัก: {', '.join(det['int'])}")
        if det["freq"]:
            info_parts.append(f"ความถี่: {', '.join(det['freq'])}")
        final_exercises.append(f"{name} ({' | '.join(info_parts)})" if info_parts else name)

    def clean_val(v):
        if not v:
            return ""
        if "#" in v:
            return v.split('#')[-1]
        return v

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


def get_patient_latest_record(patient_id):
    """
    ดึงข้อมูลดิบของผู้ป่วยเพื่อนำไป Auto-fill ในหน้าแบบฟอร์ม
    """
    if not validate_id(patient_id):
        return {"found": False}
    clean_id = str(patient_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"

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
            OPTIONAL {{ ?pe ex:visitDate_Physical ?datePE }}
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
            OPTIONAL {{ ?le ex:visitDate_Lab ?dateLab }}
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
            if "fname" in row:
                data["firstname"] = get_val(row, "fname")
            if "lname" in row:
                data["lastname"] = get_val(row, "lname")
            if "gender" in row:
                data["gender"] = get_val(row, "gender")
            if "type" in row:
                data["diabetes_type"] = get_val(row, "type")
            if "insulin" in row:
                data["insulin_use"] = get_val(row, "insulin")
            if "freq" in row:
                data["frequency"] = get_val(row, "freq")

            if "datePE" in row:
                data["checkup_date"] = get_val(row, "datePE")
            if "dateLab" in row:
                data["blood_test_date"] = get_val(row, "dateLab")

            if "weight" in row:
                data["weight"] = get_val(row, "weight")
            if "height" in row:
                data["height"] = get_val(row, "height")
            if "sbp" in row:
                data["bp_high"] = get_val(row, "sbp")
            if "dbp" in row:
                data["bp_low"] = get_val(row, "dbp")

            if "chol" in row:
                data["cholesterol"] = get_val(row, "chol")
            if "ldl" in row:
                data["ldl"] = get_val(row, "ldl")
            if "hdl" in row:
                data["hdl"] = get_val(row, "hdl")
            if "tri" in row:
                data["triglyceride"] = get_val(row, "tri")
            if "fpg" in row:
                data["fpg"] = get_val(row, "fpg")
            if "ketone" in row:
                data["ketone"] = get_val(row, "ketone")
            if "micro" in row:
                data["microalbumin"] = get_val(row, "micro")

            if "special" in row:
                v = get_val(row, "special")
                if v and v not in data["special"]:
                    data["special"].append(v)

            if "fav" in row:
                v = get_val(row, "fav")
                if v and v not in data["favorites"]:
                    data["favorites"].append(v)

        return data

    except Exception as e:
        print(f"❌ Error fetching latest record: {e}")
        return {"found": False}
    
def get_patient_streak(patient_id):
    """
    ดึงข้อมูล Streak ปัจจุบัน, สถิติสูงสุด และวันที่ออกกำลังกายล่าสุด
    (ใช้โค้ดเดิมของคุณได้เลย)
    """
    if not validate_id(patient_id):
        return {"current_streak": 0, "max_streak": 0, "last_date": ""}

    clean_id = str(patient_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    
    SELECT ?currentStreak ?maxStreak ?lastDate
    WHERE {{
        OPTIONAL {{ ex:{pid} ex:currentStreak ?currentStreak }}
        OPTIONAL {{ ex:{pid} ex:maxStreak ?maxStreak }}
        OPTIONAL {{ ex:{pid} ex:lastExerciseDate ?lastDate }}
    }}
    """
    try:
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()
        bindings = results["results"]["bindings"]

        if bindings:
            row = bindings[0]
            return {
                "current_streak": int(row.get("currentStreak", {}).get("value", 0)),
                "max_streak": int(row.get("maxStreak", {}).get("value", 0)),
                "last_date": row.get("lastDate", {}).get("value", "")
            }
    except Exception as e:
        print(f"❌ Error fetching streak data for {pid}: {e}")

    return {"current_streak": 0, "max_streak": 0, "last_date": ""}


def update_patient_streak(patient_id, new_streak, max_streak, today_date_str):
    """
    อัปเดตข้อมูล Streak ใหม่ลง GraphDB
    (ใช้โค้ดเดิมของคุณได้เลย)
    """
    if not validate_id(patient_id):
        return False

    clean_id = str(patient_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"

    update_query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    DELETE {{
        ex:{pid} ex:currentStreak ?c .
        ex:{pid} ex:maxStreak ?m .
        ex:{pid} ex:lastExerciseDate ?d .
    }}
    INSERT {{
        ex:{pid} ex:currentStreak "{int(new_streak)}"^^xsd:integer .
        ex:{pid} ex:maxStreak "{int(max_streak)}"^^xsd:integer .
        ex:{pid} ex:lastExerciseDate "{escape_sparql(today_date_str)}"^^xsd:date .
    }}
    WHERE {{
        OPTIONAL {{ ex:{pid} ex:currentStreak ?c }}
        OPTIONAL {{ ex:{pid} ex:maxStreak ?m }}
        OPTIONAL {{ ex:{pid} ex:lastExerciseDate ?d }}
    }}
    """
    try:
        sparql_write.setQuery(update_query)
        sparql_write.query()
        print(f"🔥 Updated Streak for {pid}: {new_streak} Days (Max: {max_streak})")
        return True
    except Exception as e:
        print(f"❌ Error updating streak for {pid}: {e}")
        return False


# =========================================================================
# 🔥 [ส่วนที่เพิ่มใหม่] ฟังก์ชันดึง DailyPlan ทั้งหมดมาเช็กสถานะ (Rest/Missing/Completed)
# =========================================================================
def get_patient_daily_plans(patient_id):
    """
    ดึงตารางแผนรายวันทั้งหมดของคนไข้เพื่อตรวจสอบ planStatus ในแต่ละวัน
    """
    clean_id = str(patient_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    
    SELECT ?planDate ?planStatus
    WHERE {{
        ex:{pid} ex:hasMonthlyPlan ?monthly .
        ?monthly ex:hasWeeklyPlan ?weekly .
        ?weekly ex:hasDailyPlan ?dayNode .
        
        ?dayNode ex:planDate ?planDate .
        ?dayNode ex:planStatus ?planStatus .
    }}
    ORDER BY ASC(?planDate)
    """
    try:
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()
        bindings = results["results"]["bindings"]

        plans = []
        for row in bindings:
            p_date_str = row.get("planDate", {}).get("value", "")
            status = row.get("planStatus", {}).get("value", "")

            if p_date_str:
                plans.append({
                    "date": datetime.strptime(p_date_str, "%Y-%m-%d").date(),
                    "status": status  # "Rest", "Missing", "Completed", "Pending"
                })
        return plans
    except Exception as e:
        print(f"❌ Error fetching daily plans for {pid}: {e}")
        return []


# =========================================================================
# 🔥 [ส่วนที่แก้ไข] ฟังก์ชันคำนวณ Streak ใหม่ โดยรองรับ Rest และตรวจเช็ก Missing
# =========================================================================
def process_patient_streak_on_complete(patient_id):
    """
    เรียกใช้เมื่อผู้ป่วยออกกำลังกายเสร็จ ( completed = True )
    ระบบจะคำนวณ Streak ใหม่โดยตรวจสอบว่าระหว่างวันที่เล่นครั้งล่าสุดจนถึงวันนี้
    มีวันที่ขาดออกกำลังกาย ( Missing ) หรือไม่
    """
    today_date = date.today()
    today_str = today_date.strftime("%Y-%m-%d")

    # 1. ดึงข้อมูล Streak ปัจจุบัน
    streak_info = get_patient_streak(patient_id)
    current_streak = streak_info.get("current_streak", 0)
    max_streak = streak_info.get("max_streak", 0)
    last_date_str = streak_info.get("last_date", "")

    # 2. คำนวณ Streak ตามเงื่อนไข
    if not last_date_str:
        # กรณีที่ 1: เพิ่งเล่นครั้งแรก
        new_streak = 1
    else:
        # แปลงวันที่ออกกำลังกายล่าสุด
        clean_last_date = last_date_str.split("T")[0].split(" ")[0]
        last_date = datetime.strptime(clean_last_date, "%Y-%m-%d").date()

        if last_date == today_date:
            # กรณีออกกำลังกายซ้ำในวันเดียวกัน ให้ใช้ค่า Streak เดิม
            new_streak = current_streak if current_streak > 0 else 1
        else:
            # ดึงตารางรายวันจาก GraphDB มาเช็กสถานะระหว่างช่วงวัน
            daily_plans = get_patient_daily_plans(patient_id)
            has_missing_day = False

            # วนเช็กเฉพาะวันที่อยู่ระหว่าง last_date ถึง ก่อนวันนี้ (today_date)
            for plan in daily_plans:
                p_date = plan["date"]
                p_status = plan["status"]

                if last_date < p_date < today_date:
                    # ถ้าเจอวันไหนที่เป็น "Missing" แสดงว่าขาดการออกกำลังกาย
                    if p_status == "Missing":
                        has_missing_day = True
                        break

            if has_missing_day:
                # กรณีที่ 2: มีวันขาดออกกำลังกาย (Missing) -> รีเซ็ตเริ่ม 1
                new_streak = 1
            else:
                # กรณีที่ 3: ไม่มีวัน Missing (มีแต่ Rest หรือ Completed) -> นับ Streak ต่อ! 🔥
                new_streak = current_streak + 1

    # อัปเดต Max Streak ถ้าทำสถิติใหม่ได้
    new_max = max(new_streak, max_streak)

    # 3. เซฟลง GraphDB
    update_patient_streak(patient_id, new_streak, new_max, today_str)

    return {
        "current_streak": new_streak,
        "max_streak": new_max,
        "last_date": today_str
    }