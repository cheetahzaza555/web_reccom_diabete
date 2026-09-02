from flask import Blueprint, request, abort
import os
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from modules.db.connection import sparql_write  # เรียกใช้ sparql_write จากระบบเดิม

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
            # คำสั่ง SPARQL สำหรับลบ LINE UID ปัจจุบันออกจากระบบ
            delete_query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            DELETE {{ ?patient ex:hasLineUID "{line_uid}" }}
            WHERE {{ ?patient ex:hasLineUID "{line_uid}" }}
            """
            sparql_write.setQuery(delete_query)
            sparql_write.query()

            reply_text = "❌ ยกเลิกการผูกบัญชีและปิดการแจ้งเตือนเรียบร้อยแล้วครับ ระบบจะหยุดส่งข้อความแจ้งเตือนจนกว่าคุณจะผูกบัญชีใหม่อีกครั้งครับ"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            
        except Exception as e:
            print(f"Error Unbinding: {e}")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="เกิดข้อผิดพลาดในการยกเลิกบัญชี กรุณาลองใหม่อีกครั้งครับ"))
        return

    # 🔵 3. โค้ดเดิมของคุณ: ดักจับการพิมพ์รหัส (เช่น #8604b742) เพื่อบันทึกลง GraphDB
    elif user_msg.startswith('#'):
        patient_id = user_msg[1:]  # ตัดเครื่องหมาย # ออก จะเหลือแค่ 8604b742
        
        try:
            # 💾 บันทึก LINE UID ลงใน GraphDB ผูกกับ Patient Node
            query = f"""
            PREFIX ex: <http://example.org/diabetes#>
            DELETE {{ ex:Patient{patient_id} ex:hasLineUID ?oldUid }}
            INSERT {{ ex:Patient{patient_id} ex:hasLineUID "{line_uid}" }}
            WHERE {{
                OPTIONAL {{ ex:Patient{patient_id} ex:hasLineUID ?oldUid }}
            }}
            """
            sparql_write.setQuery(query)
            sparql_write.query()

            # ส่งข้อความตอบกลับเพื่อยืนยันว่าผูกบัญชีสำเร็จ
            reply_text = f"✅ ผูกบัญชีเข้ากับระบบ DiaBalance (รหัส: {patient_id}) สำเร็จ! ระบบจะเริ่มส่งแจ้งเตือนตารางออกกำลังกายให้คุณที่นี่ครับ"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        except Exception as e:
            print(f"Error Binding: {e}")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="เกิดข้อผิดพลาดในการบันทึกข้อมูลเข้าระบบครับ"))
        return