# modules/email_utils.py
import smtplib
from email.mime.text import MIMEText
import os

def send_otp_email(receiver_email, otp_code, action="register"):
    sender_email = os.getenv("email_otp")
    app_password = os.getenv("app_password ")
    
    # 🌟 1. เช็กว่า action คืออะไร เพื่อเปลี่ยนข้อความให้ตรงกับบริบท
    if action == "update_settings":
        subject = "รหัส OTP ยืนยันการเปลี่ยนแปลงข้อมูลส่วนตัว - DiaBalance"
        body_text = f"รหัส OTP สำหรับยืนยันการแก้ไขข้อมูลส่วนตัว DiaBalance คือ: {otp_code}\n\nกรุณานำรหัสนี้ไปกรอกในหน้าเว็บเพื่อยืนยันตัวตน (รหัสมีอายุการใช้งาน 10 นาที)"
    elif action == "forgot_password":
        subject = "รหัส OTP สำหรับรีเซ็ตรหัสผ่าน - DiaBalance"
        body_text = f"รหัส OTP สำหรับตั้งรหัสผ่านใหม่ของคุณคือ: {otp_code}\n\nหากคุณไม่ได้ทำรายการนี้ โปรดเพิกเฉยต่ออีเมลฉบับนี้ (รหัสมีอายุการใช้งาน 10 นาที)"
    else:
        # ค่าเริ่มต้นจะเป็น Register เสมอ (เผื่อไม่ได้ส่ง action มา)
        subject = "รหัส OTP ยืนยันการสมัครสมาชิก - DiaBalance"
        body_text = f"รหัส OTP สำหรับยืนยันการสมัครสมาชิก DiaBalance คือ: {otp_code}\n\nกรุณานำรหัสนี้ไปกรอกในหน้าเว็บเพื่อยืนยันตัวตน (รหัสมีอายุการใช้งาน 10 นาที)"

    # 🌟 2. นำข้อความที่แยกไว้มาใส่ใน MIMEText และ Subject
    msg = MIMEText(body_text)
    msg['Subject'] = subject
    msg['From'] = f"DiaBalance <{sender_email}>"
    msg['To'] = receiver_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Email Error: {e}")
        return False