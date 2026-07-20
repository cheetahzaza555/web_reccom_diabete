import os
import datetime
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.exceptions import LineBotApiError
from modules.db.connection import sparql_read  # ⚠️ ตรวจสอบ path ของ sparql_read ให้ตรงกับโปรเจกต์คุณด้วยนะครับ

# โหลด Token จาก .env
LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)

def send_exercise_reminder(line_uid, exercise_name):
    """ฟังก์ชันสำหรับส่งข้อความแจ้งเตือนให้ผู้ใช้ตาม UID"""
    try:
        message = f"🔔 สวัสดีครับ! วันนี้คุณมีตารางออกกำลังกายท่า: {exercise_name}\nอย่าลืมหาเวลามาขยับร่างกายเพื่อสุขภาพที่ดีนะครับ 💪"
        line_bot_api.push_message(line_uid, TextSendMessage(text=message))
        print(f"✅ ส่งแจ้งเตือนให้ {line_uid} สำเร็จ")
    except LineBotApiError as e:
        print(f"❌ ส่งแจ้งเตือนล้มเหลว: {e}")

def run_morning_reminder_job():
    """หุ่นยนต์ตัวนี้จะตื่นมาตอนเช้า เพื่อดึงข้อมูลแล้วสั่งส่งไลน์"""
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    print(f"🌅 เริ่มทำงาน: แจ้งเตือนตารางออกกำลังกายประจำวันที่ {today_str}")
    
    # 🌟 เพิ่ม PREFIX rdfs และแก้การดึงชื่อเป็น rdfs:label
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?uid ?exerciseName
    WHERE {{
        # 1. หาคนไข้ที่มี LINE UID และมีแผนรายเดือน
        ?patient ex:hasLineUID ?uid .
        ?patient ex:hasMonthlyPlan ?month .
        
        # 2. เจาะลึกจากเดือน -> สัปดาห์ -> วัน
        ?month ex:hasWeeklyPlan ?week .
        ?week ex:hasDailyPlan ?dayNode .
        
        # 3. กรองเอาเฉพาะ "วันนี้" ที่สถานะเป็น "Pending"
        ?dayNode ex:planDate "{today_str}"^^xsd:date .
        ?dayNode ex:planStatus "Pending" .
        
        # 4. ดึงชื่อท่าออกกำลังกาย
        ?dayNode ex:hasScheduledExercise ?ex .
        
        # พยายามดึงชื่อจาก rdfs:label ถ้าไม่มีให้ใช้รหัสแทน (กันเหนียวไว้เผื่อบางท่าลืมใส่ชื่อ)
        OPTIONAL {{ ?ex rdfs:label ?labelName }}
        BIND(COALESCE(?labelName, STRAFTER(STR(?ex), "#")) AS ?exerciseName)
    }}
    """
    
    try:
        sparql_read.setQuery(query)
        sparql_read.setReturnFormat('json')
        results = sparql_read.query().convert()
        
        bindings = results["results"]["bindings"]
        
        if not bindings:
            print("ไม่มีตารางที่ต้องแจ้งเตือนในวันนี้ครับ (หรือคนที่มีตารางยังไม่ได้ผูก LINE UID)")
            return
            
        # 2. วนลูปรายชื่อคน แล้วเรียกใช้ฟังก์ชันส่งข้อความ
        for result in bindings:
            uid = result["uid"]["value"]
            # ดึงชื่อท่าที่ได้จาก SPARQL (ถ้าเป็นภาษาไทย จะแสดงผลสวยงามเลย)
            exercise_name = result.get("exerciseName", {}).get("value", "ตามแผนของวันนี้")
            
            # เรียกใช้ฟังก์ชันส่งข้อความ LINE
            send_exercise_reminder(uid, exercise_name)
            
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดึงข้อมูลหรือแจ้งเตือน: {e}")