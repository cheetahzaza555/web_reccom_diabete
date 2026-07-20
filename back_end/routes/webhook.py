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
    line_uid = event.source.user_id  # 🌟 นี่คือรหัส UID ที่เราต้องการ!

    # ตรวจสอบว่าผู้ใช้พิมพ์ข้อความขึ้นต้นด้วย # (เช่น #8604b742)
    if user_msg.startswith('#'):
        patient_id = user_msg[1:]  # ตัดเครื่องหมาย # ออก จะเหลือแค่ 8604b742
        
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