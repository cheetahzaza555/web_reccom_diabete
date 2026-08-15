# modules/db/plan_repository.py
"""
ฟังก์ชันจัดการตารางออกกำลังกาย (แผน 30 วัน, ตารางรายสัปดาห์/รายวัน)
"""

import uuid
import datetime
from .connection import sparql_read, sparql_write, escape_sparql, safe_get_name


def generate_30_days_plan(patient_id, exercise_id, exact_dates_list, daily_target_minutes):
    print(f"👉 เช็กค่า exercise_id ที่รับมา: '{exercise_id}'")
    pid = f"Patient{patient_id}"  # ใช้ ID ดั้งเดิม
    start_date = datetime.datetime.today().date()

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
        for r in results:
            day_id = safe_get_name(r["dayNode"]["value"])
            date_str = r["date"]["value"]
            status = r.get("status", {}).get("value", "Rest")
            duration = int(r.get("duration", {}).get("value", 0))
            ex_name = r.get("exName", {}).get("value", None)
            ex_original_id = r.get("exId", {}).get("value", None)

            is_exercise_day = status in ["Pending", "Completed", "Missed"]
            is_completed = (status == "Completed")

            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

            schedule.append({
                "id": day_id,  # ใช้ชื่อ Node แทน ID ใน SQL
                "day_of_week": date_obj.weekday(),
                "is_exercise_day": is_exercise_day,
                "exercise_name": ex_name,
                "exercise_id": ex_original_id,  # เก็บ ID ท่าไว้ใช้ตอนกดเข้าไปดูวิดีโอ
                "completed": is_completed,
                "duration_minutes": duration,
                "date_obj": date_obj,
                "status": status,
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
    # 🌟 1. เพิ่ม ?youtubeId ตรง SELECT
    SELECT ?status ?duration ?exName ?exId ?youtubeId
    WHERE {{
        OPTIONAL {{ ex:{day_node_id} ex:planStatus ?status }}
        OPTIONAL {{ ex:{day_node_id} ex:durationMinutes ?duration }}
        OPTIONAL {{ 
            ex:{day_node_id} ex:hasScheduledExercise ?ex .
            BIND(STRAFTER(STR(?ex), "#") AS ?exId)
            OPTIONAL {{ ?ex rdfs:label ?label }}
            BIND(COALESCE(?label, ?exId) AS ?exName)
            
            # 🌟 2. เพิ่มการดึง ID ของวิดีโอ (ถ้ามี)
            OPTIONAL {{ ?ex ex:hasYoutubeID ?youtubeId }}
        }}
    }} LIMIT 1
    """
    try:
        sparql_read.setQuery(query)
        res = sparql_read.query().convert()["results"]["bindings"]
        if not res:
            return None

        r = res[0]
        return {
            "exercise_name": r.get("exName", {}).get("value", ""),
            "exercise_id": r.get("exId", {}).get("value", ""),
            "completed": r.get("status", {}).get("value", "") == "Completed",
            "target_minutes": int(r.get("duration", {}).get("value", 30)),
            # 🌟 3. ดึงค่าส่งออกไปให้ Flask ถ้าไม่มีคลิปจะได้เป็นค่า None
            "youtube_id": r.get("youtubeId", {}).get("value", None)
        }
    except Exception as e:
        print(f"❌ Error getting daily plan info: {e}")
        return None

def update_schedule_status(plan_id, new_status):
    """
    ฟังก์ชันสำหรับอัปเดต ex:status ใน GraphDB
    """
    sparql_query = f"""
    PREFIX ex: <http://example.org/>
    
    DELETE {{
        ex:{plan_id} ex:status ?oldStatus .
    }}
    INSERT {{
        ex:{plan_id} ex:status "{new_status}" .
    }}
    WHERE {{
        OPTIONAL {{ ex:{plan_id} ex:status ?oldStatus . }}
    }}
    """
    # รันคำสั่ง SPARQL UPDATE ผ่านตัวเชื่อมต่อ GraphDB ของคุณ
    # execute_sparql_update(sparql_query)