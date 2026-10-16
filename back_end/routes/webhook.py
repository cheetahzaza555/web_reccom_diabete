from flask import Blueprint, request, abort
import os
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from modules.db.connection import sparql_read, sparql_write, validate_id, escape_sparql

webhook_bp = Blueprint('webhook', __name__)

# ดึง Token จาก .env
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

@webhook_bp.route("/callback", methods=['POST'])
def callback():
    # รับค่า Signature และข้อมูลที่ LINE ส่งมา
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    line_uid = event.source.user_id  # 🌟 รหัส UID ของผู้ใช้

    # 🟢 1. ดักจับผู้ใช้กดปุ่ม "ผูกบัญชี" จาก Rich Menu
    if user_msg in ["ผูกบัญชี", "ผูกบัญชีเข้ากับระบบ", "วิธีผูกบัญชี"]:
        reply_text = (
            "กรุณาพิมพ์รหัสประจำตัวที่ได้จากหน้าเว็บไซต์ (เช่น #12345678) แล้วส่งมาในแชทนี้ เพื่อยืนยันการผูกบัญชี 🔗\n\n"
            "💡 หลังจากผูกบัญชีสำเร็จแล้ว ระบบจะส่งการแจ้งเตือนตารางออกกำลังกายในแต่ละวันให้คุณผ่านแชทนี้ 💪"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return

    # 🔴 2. ดักจับผู้ใช้กดปุ่ม "ยกเลิกการผูกบัญชี" จาก Rich Menu
    elif user_msg == "ยกเลิกการผูกบัญชี":
        try:
            safe_uid = escape_sparql(line_uid)
            # คำสั่ง SPARQL สำหรับลบ LINE UID ปัจจุบันออกจากระบบ
            delete_query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            DELETE {{ ?patient ex:hasLineUID "{safe_uid}" }}
            WHERE {{ ?patient ex:hasLineUID "{safe_uid}" }}
            """
            sparql_write.setQuery(delete_query)
            sparql_write.query()

            reply_text = "❌ ยกเลิกการผูกบัญชีและปิดการแจ้งเตือนเรียบร้อยแล้วครับ ระบบจะหยุดส่งข้อความแจ้งเตือนจนกว่าคุณจะผูกบัญชีใหม่อีกครั้งครับ"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            
        except Exception as e:
            print(f"Error Unbinding: {e}")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="เกิดข้อผิดพลาดในการยกเลิกบัญชี กรุณาลองใหม่อีกครั้งครับ"))
        return

    # 🔵 3. ดักจับการพิมพ์รหัสยืนยันตัวตน (เช่น #8604b742) เพื่อตรวจสอบก่อนผูกบัญชี
    elif user_msg.startswith('#'):
        raw_id = user_msg[1:].strip()
        patient_id = raw_id.replace("Patient", "").strip()

        # 3.1 ตรวจสอบรูปแบบ ID
        if not patient_id or not validate_id(patient_id):
            reply_text = (
                "❌ รูปแบบรหัสไม่ถูกต้องครับ\n"
                "กรุณาพิมพ์เครื่องหมาย # ตามด้วยรหัสประจำตัวของคุณ เช่น #8604b742 ครับ"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            return

        try:
            pid = f"Patient{patient_id}"
            safe_uid = escape_sparql(line_uid)

            # 3.2 🔍 ตรวจสอบว่าบัญชีผู้ป่วยนี้มีอยู่จริงในระบบหรือไม่
            check_query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            SELECT ?fname ?lname ?uname WHERE {{
                ex:{pid} a ex:Patient .
                OPTIONAL {{ ex:{pid} ex:firstname ?fname }}
                OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
                OPTIONAL {{ ex:{pid} ex:username ?uname }}
            }} LIMIT 1
            """
            sparql_read.setQuery(check_query)
            sparql_read.setReturnFormat('json')
            results = sparql_read.query().convert()
            bindings = results.get("results", {}).get("bindings", [])

            # 🚨 ถ้าไม่พบบัญชีนี้ในฐานข้อมูลจริง ปฏิเสธทันที ไม่สร้าง Node ปลอม
            if not bindings:
                reply_text = (
                    f"❌ ไม่พบรหัสผู้ใช้งาน #{patient_id} ในระบบ DiaBalance ครับ\n\n"
                    "กรุณาตรวจสอบรหัสประจำตัวของคุณอีกครั้งจากหน้าเว็บไซต์ "
                    "(ดูได้ที่หัวข้อ 'รับการแจ้งเตือนผ่าน LINE' บนหน้าหลัก) แล้วลองใหม่อีกครั้ง 🔍"
                )
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                return

            # 3.3 ดึงข้อมูลชื่อผู้ใช้
            row = bindings[0]
            fname = row.get("fname", {}).get("value", "").strip()
            lname = row.get("lname", {}).get("value", "").strip()
            uname = row.get("uname", {}).get("value", "").strip()
            fullname = f"{fname} {lname}".strip()
            user_display = fullname or uname

            # 3.4 💾 บันทึก LINE UID ลงใน GraphDB
            # ลบการผูกเก่าของบัญชีนี้ และลบ LINE UID นี้ออกจากบัญชีอื่น (ป้องกันการผูกซ้อน)
            bind_query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            DELETE {{
                ex:{pid} ex:hasLineUID ?oldUid .
                ?otherPatient ex:hasLineUID "{safe_uid}" .
            }}
            INSERT {{
                ex:{pid} ex:hasLineUID "{safe_uid}" .
            }}
            WHERE {{
                OPTIONAL {{ ex:{pid} ex:hasLineUID ?oldUid }}
                OPTIONAL {{ ?otherPatient ex:hasLineUID "{safe_uid}" }}
            }}
            """
            sparql_write.setQuery(bind_query)
            sparql_write.query()

            # ส่งข้อความตอบกลับยืนยันพร้อมระบุชื่อผู้ใช้
            name_text = f"คุณ {user_display} " if user_display else ""
            reply_text = (
                f"✅ ผูกบัญชีเข้ากับระบบ DiaBalance สำเร็จเรียบร้อยแล้วครับ!\n\n"
                f"👤 บัญชี: {name_text}(รหัส: #{patient_id})\n\n"
                f"ระบบจะเริ่มส่งข้อความแจ้งเตือนตารางออกกำลังกายประจำวันให้คุณทางแชทนี้ 💪"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

        except Exception as e:
            print(f"Error Binding: {e}")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="เกิดข้อผิดพลาดในการบันทึกข้อมูลเข้าระบบ กรุณาลองใหม่อีกครั้งครับ"))
        return

    # 4. ข้อความทั่วไปอื่นๆ
    else:
        reply_text = (
            "สวัสดี 👋 หากต้องการผูกบัญชีเพื่อรับการแจ้งเตือนตารางออกกำลังกาย\n"
            "กรุณาพิมพ์เครื่องหมาย # ตามด้วยรหัสประจำตัวของคุณ (เช่น #8604b742) แล้วส่งมาในแชทนี้ 🔗\n\n"
            "หรือหากต้องการยกเลิกการผูกบัญชี สามารถพิมพ์ว่า 'ยกเลิกการผูกบัญชี' "
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        return
