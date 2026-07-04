# modules/db/exercise_repository.py
"""
ฟังก์ชันจัดการข้อมูลท่าออกกำลังกาย: รายการแนะนำ, รายละเอียดท่า, คลังท่าทั้งหมด
"""

from SPARQLWrapper import JSON
from .connection import sparql_read

# Mapping หมวดหมู่ภาษาไทย (ใช้ร่วมกันหลายฟังก์ชันในไฟล์นี้)
CATEGORY_MAP_TH = {
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

# ลำดับความสำคัญของหมวดหมู่ (ตัวที่เจาะจงกว่าอยู่บนสุด)
PRIORITY_ORDER = [
    "NonWeightBearingAerobicSport", "WeightBearingAerobicSport",
    "NonWeightBearingResistanceExercise", "WeightBearingResistanceExercise",
    "Walking", "Running", "Dancing", "Bicycling", "WaterActivity",
    "Aerobic", "Resistance", "StretchingExercise"
]

# Mapping ชื่อคลาสกับไฟล์รูปภาพ
IMG_MAP = {
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
    "stretchingexercise": "flexibility.png",
    "aerobic": "aerobic.png",
    "resistance": "resistance.png"
}


def get_all_recommendations(patient_id):
    """
    ดึงรายการท่าออกกำลังกายแนะนำ พร้อมรายละเอียด (ชื่อ, ความหนัก, ประเภท)
    """
    # จัดการเรื่อง ID ให้ถูกต้อง: ลบ "Patient" ออกก่อนกันเหนียว แล้วเติมกลับให้เหลือครั้งเดียว
    clean_id = patient_id.replace("Patient", "")
    pid_resource = f"Patient{clean_id}"

    print(f"🔍 Searching GraphDB for: ex:{pid_resource}")

    # ใช้ UNION กันเหนียวเรื่องชื่อ Property (บางทีพิมพ์ผิด recommendedExercise/recommendExercise)
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?recId ?label ?met ?categoryName
    WHERE {{
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

        for r in results["results"]["bindings"]:
            ex_id = r["recId"]["value"]
            ex_name = r["label"]["value"] if "label" in r else ex_id
            ex_met = r["met"]["value"] if "met" in r else "-"

            raw_cat = r["categoryName"]["value"] if "categoryName" in r else "ทั่วไป"
            ex_cat = CATEGORY_MAP_TH.get(raw_cat, raw_cat)

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


def get_exercise_details_by_id(exercise_id):
    """
    ดึงรายละเอียดของท่าออกกำลังกาย 1 ท่า (จาก ID) เพื่อเอาไปแสดงผล (Preview)
    """
    if "http" in exercise_id:
        ex_resource = f"<{exercise_id}>"
    else:
        ex_resource = f"ex:{exercise_id}"

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?label ?met ?categoryName
    WHERE {{
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

            cat_map = {"Running": "การวิ่ง", "Walking": "การเดิน", "Bicycling": "จักรยาน"}
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


def _choose_category(raw_names):
    """เลือกหมวดหมู่หลักจากรายชื่อ type ทั้งหมดตามลำดับความสำคัญ"""
    for p_name in PRIORITY_ORDER:
        if p_name in raw_names:
            return p_name
    return raw_names[0] if raw_names else ""


def _get_image_for_category(chosen_name):
    """หา path รูปภาพจากชื่อหมวดหมู่ที่เลือก"""
    search_key = chosen_name.lower()
    if search_key in IMG_MAP:
        return IMG_MAP[search_key]

    # Fallback: ค้นหาตัวที่ยาวที่สุดที่แมตช์ได้
    sorted_keys = sorted(IMG_MAP.keys(), key=len, reverse=True)
    for k in sorted_keys:
        if k in search_key:
            return IMG_MAP[k]
    return "exercise_default.png"


def get_all_exercises_for_library():
    """ดึงรายการท่าออกกำลังกายทั้งหมดสำหรับหน้าคลังท่า (library)"""
    query = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?id ?name  ?mets ?youtube_id (GROUP_CONCAT(DISTINCT ?typeUri; separator=",") AS ?allTypes)
    WHERE {
        ?s a ?typeUri .
        ?typeUri rdfs:subClassOf* ex:Exercise . 
        FILTER(?typeUri != ex:Exercise)

        BIND(STRAFTER(STR(?s), "#") AS ?id)
        OPTIONAL { ?s rdfs:label ?name }
        OPTIONAL { ?s ex:metValue ?mets }
        OPTIONAL { ?s ex:hasYoutubeID ?youtube_id }
    }
    GROUP BY ?id ?name ?mets ?youtube_id
    """
    try:
        sparql_read.setQuery(query)
        sparql_read.setReturnFormat(JSON)
        results = sparql_read.query().convert()

        exercises = []

        for r in results["results"]["bindings"]:
            def val(key):
                return r[key]["value"] if key in r else ""

            types_list = val("allTypes").split(',')
            raw_names = [t.split('#')[-1] for t in types_list]

            chosen_name = _choose_category(raw_names)
            img_file = _get_image_for_category(chosen_name)

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
    """ดึงรายละเอียดเต็มของท่าออกกำลังกาย 1 ท่า (สำหรับหน้ารายละเอียด/เริ่มออกกำลังกาย)"""
    print(f"👉 เช็กค่า exercise_id ที่รับมา: '{ex_id}'")

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?name ?desc ?mets ?youtube_id
            (GROUP_CONCAT(DISTINCT ?typeUri; separator=",") AS ?allTypes)
            (GROUP_CONCAT(DISTINCT ?step; separator="|") AS ?stepsRaw)
            (GROUP_CONCAT(DISTINCT ?precaution; separator="|") AS ?precautionsRaw)
    WHERE {{
        BIND(ex:{ex_id} AS ?s)
        ?s rdfs:label ?name .
        ?s a ?typeUri .
        ?typeUri rdfs:subClassOf* ex:Exercise .
        FILTER(?typeUri != ex:Exercise)
        
        OPTIONAL {{ ?s ex:description ?desc }}
        OPTIONAL {{ ?s ex:metValue ?mets }}
        OPTIONAL {{ ?s ex:hasYoutubeID ?youtube_id }}

        OPTIONAL {{ 
            ?source ex:hasStep ?step .
            FILTER(?source = ?s || ?source = ?typeUri)
        }}
        OPTIONAL {{ 
            ?source ex:hasPrecaution ?precaution .
            FILTER(?source = ?s || ?source = ?typeUri)
        }}
    }}
    GROUP BY ?name ?desc ?mets ?youtube_id
    """

    try:
        sparql_read.setQuery(query)
        results = sparql_read.query().convert()

        if not results["results"]["bindings"]:
            return None

        r = results["results"]["bindings"][0]

        def val(key):
            return r[key]["value"] if key in r else ""

        types_list = val("allTypes").split(',')
        raw_names = [t.split('#')[-1] for t in types_list]
        chosen_name = _choose_category(raw_names)
        img_file = _get_image_for_category(chosen_name)

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
            "video": yt_id
        }

    except Exception as e:
        print(f"Error in get_exercise_by_id: {e}")
        return None