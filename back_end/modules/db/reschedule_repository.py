# ============================================================
# ไฟล์: modules/db/reschedule_repository.py
# หน้าที่: เลื่อนตารางออกกำลังกายอัตโนมัติ เมื่อผู้ใช้พลาดวันที่กำหนดไว้
# (แยกออกมาจาก plan_repository.py เพื่อความชัดเจนของ responsibility)
# ============================================================

import datetime
from .connection import sparql_read, sparql_write, escape_sparql, safe_get_name


def _get_full_schedule_rows(patient_id):
    """
    ดึงตารางทั้งหมดของ patient พร้อม weekNode (ใช้สำหรับ reschedule)
    เรียงตามวันที่จากเก่าไปใหม่
    """
    pid = f"Patient{patient_id}"
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?dayNode ?week ?date ?status ?duration ?exId
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
        }}
    }}
    ORDER BY ?date
    """
    sparql_read.setQuery(query)
    results = sparql_read.query().convert()["results"]["bindings"]

    rows = []
    for r in results:
        rows.append({
            "day_node": safe_get_name(r["dayNode"]["value"]),
            "week_node": safe_get_name(r["week"]["value"]),
            "date": datetime.datetime.strptime(r["date"]["value"], "%Y-%m-%d").date(),
            "status": r.get("status", {}).get("value", "Rest"),
            "duration": int(r.get("duration", {}).get("value", 0)),
            "exercise_id": r.get("exId", {}).get("value", None),
        })
    return rows


def _find_first_missed_day(rows, today):
    """หาวันออกกำลังกายแรกสุดที่ผ่านมาแล้วแต่ยัง Pending (= พลาด)"""
    for i, row in enumerate(rows):
        if row["date"] < today and row["status"] == "Pending":
            return i
    return None


def _mark_day_missed(day_node_id):
    """เปลี่ยนสถานะวันที่พลาดเป็น Missed (เก็บไว้เป็นประวัติ ไม่ลบทิ้ง)"""
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    DELETE {{ ex:{day_node_id} ex:planStatus ?oldStatus }}
    INSERT {{ ex:{day_node_id} ex:planStatus "Missed" }}
    WHERE  {{ ex:{day_node_id} ex:planStatus ?oldStatus }}
    """
    sparql_write.setQuery(query)
    sparql_write.query()


def _set_day_content(day_node_id, status, duration, exercise_id):
    """เขียนทับ status / duration / hasScheduledExercise ของ day node ที่มีอยู่แล้ว"""
    exercise_insert = (
        f'ex:{day_node_id} ex:hasScheduledExercise ex:{escape_sparql(exercise_id)} .'
        if exercise_id else ""
    )

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    DELETE {{
        ex:{day_node_id} ex:planStatus ?oldStatus .
        ex:{day_node_id} ex:durationMinutes ?oldDuration .
        ex:{day_node_id} ex:hasScheduledExercise ?oldEx .
    }}
    INSERT {{
        ex:{day_node_id} ex:planStatus "{status}" .
        ex:{day_node_id} ex:durationMinutes "{duration}"^^xsd:integer .
        {exercise_insert}
    }}
    WHERE {{
        OPTIONAL {{ ex:{day_node_id} ex:planStatus ?oldStatus }}
        OPTIONAL {{ ex:{day_node_id} ex:durationMinutes ?oldDuration }}
        OPTIONAL {{ ex:{day_node_id} ex:hasScheduledExercise ?oldEx }}
    }}
    """
    sparql_write.setQuery(query)
    sparql_write.query()


def _create_new_day(week_node_id, day_node_id, date_obj, status, duration, exercise_id):
    """สร้าง DailyPlan node ใหม่ ต่อท้ายแผนเดิม (กรณีแผนถูกยืดออกไปเกินวันสุดท้ายเดิม)"""
    exercise_triple = (
        f"ex:{day_node_id} ex:hasScheduledExercise ex:{escape_sparql(exercise_id)} ."
        if exercise_id else ""
    )
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT DATA {{
        ex:{day_node_id} a ex:DailyPlan ;
            ex:planDate "{date_obj.isoformat()}"^^xsd:date ;
            ex:planStatus "{status}" ;
            ex:durationMinutes "{duration}"^^xsd:integer .
        {exercise_triple}
        ex:{week_node_id} ex:hasDailyPlan ex:{day_node_id} .
    }}
    """
    sparql_write.setQuery(query)
    sparql_write.query()


def reschedule_missed_days(patient_id, today=None):
    """
    เช็คและเลื่อนตารางทั้งชุด (domino shift) ถ้ามีวันที่พลาด
    วนซ้ำ (while) เพื่อรองรับกรณีพลาดติดกันหลายวันในการรันครั้งเดียว
    คืนค่า True ถ้ามีการเลื่อนตารางเกิดขึ้นจริง
    """
    if today is None:
        today = datetime.datetime.today().date()

    changed = False

    while True:
        rows = _get_full_schedule_rows(patient_id)
        missed_idx = _find_first_missed_day(rows, today)
        if missed_idx is None:
            break  # ไม่มีวันพลาดแล้ว จบการเลื่อน

        missed_row = rows[missed_idx]
        tail = rows[missed_idx:]  # รวมวันที่พลาดเองเป็นตัวแรก

        # 1) mark วันที่พลาดเป็น Missed (ประวัติ)
        _mark_day_missed(missed_row["day_node"])

        # 2) ลำดับ "เนื้อหา" ของวันที่เหลือทั้งหมด (status/duration/exercise)
        #    ที่จะถูกเลื่อนไปข้างหน้า 1 วัน
        tail_content = [(r["status"], r["duration"], r["exercise_id"]) for r in tail]

        start_date = missed_row["date"] + datetime.timedelta(days=1)
        last_week_node = rows[-1]["week_node"]  # ผูกวันใหม่ (ถ้าต้องสร้าง) เข้ากับสัปดาห์สุดท้าย

        # หาเลข Day ล่าสุดจากชื่อ node เพื่อสร้างชื่อ node วันใหม่ต่อเนื่อง
        last_day_node = rows[-1]["day_node"]  # เช่น DailyPlan_Patient3_ab12cd34_Day30
        prefix, last_n_str = last_day_node.rsplit("Day", 1)
        last_n = int(last_n_str)

        for offset, (status, duration, exercise_id) in enumerate(tail_content):
            new_date = start_date + datetime.timedelta(days=offset)
            # ตำแหน่งเดิมในตารางที่จะรับ "เนื้อหา" นี้ไปแทน (index ถัดจากวันพลาด)
            target_row = tail[offset + 1] if (offset + 1) < len(tail) else None

            if target_row:
                # มี day node เดิมอยู่แล้วที่วันนี้ -> เขียนทับด้วย type ใหม่
                _set_day_content(target_row["day_node"], status, duration, exercise_id)
            else:
                # เกินวันสุดท้ายเดิมของแผน -> สร้างวันใหม่ต่อท้าย
                last_n += 1
                new_day_node = f"{prefix}Day{last_n}"
                _create_new_day(last_week_node, new_day_node, new_date, status, duration, exercise_id)

        changed = True

    return changed


def get_all_patients_with_active_plan():
    """ดึง patient_id ทั้งหมดที่ยังมีวันออกกำลังกายค้างอยู่ (status = Pending)"""
    query = """
    PREFIX ex: <http://example.org/diabetes#>
    SELECT DISTINCT ?patient WHERE {
        ?patient ex:hasMonthlyPlan ?m .
        ?m ex:hasWeeklyPlan ?w .
        ?w ex:hasDailyPlan ?d .
        ?d ex:planStatus "Pending" .
    }
    """
    sparql_read.setQuery(query)
    results = sparql_read.query().convert()["results"]["bindings"]

    patient_ids = []
    for r in results:
        name = safe_get_name(r["patient"]["value"])  # เช่น "Patient3"
        patient_ids.append(name.replace("Patient", ""))
    return patient_ids


def run_daily_reschedule_job():
    """Entry point สำหรับ scheduler เรียกทุกเที่ยงคืน"""
    today = datetime.datetime.today().date()
    patient_ids = get_all_patients_with_active_plan()

    for pid in patient_ids:
        try:
            changed = reschedule_missed_days(pid, today=today)
            if changed:
                print(f"[reschedule] เลื่อนตารางให้ Patient{pid} เรียบร้อย")
        except Exception as e:
            print(f"[reschedule] เกิดข้อผิดพลาดกับ Patient{pid}: {e}")

    print(f"[reschedule] ตรวจสอบครบทุก patient แล้ว ({len(patient_ids)} คน)")