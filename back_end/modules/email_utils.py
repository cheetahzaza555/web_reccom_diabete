# modules/email_utils.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
import os


def _generate_email_content(action, otp_code):
    """
    สร้าง Subject, Plain-text fallback และ HTML Email Template ที่ปรับแต่งตาม action
    """
    if action == "update_settings":
        subject = "รหัส OTP ยืนยันการเปลี่ยนแปลงข้อมูลส่วนตัว - DiaBalance"
        action_title = "ยืนยันการเปลี่ยนแปลงข้อมูลส่วนตัว"
        action_desc = "ระบบได้รับคำขอเปลี่ยนแปลงข้อมูลส่วนตัวในบัญชี DiaBalance ของคุณ กรุณาใช้รหัส OTP ด้านล่างเพื่อยืนยันการทำรายการ:"
        security_note = "หากคุณไม่ได้เป็นผู้ทำรายการนี้ โปรดตรวจสอบความปลอดภัยของบัญชีหรือเปลี่ยนรหัสผ่านทันที"
    elif action == "forgot_password":
        subject = "รหัส OTP สำหรับรีเซ็ตรหัสผ่าน - DiaBalance"
        action_title = "รีเซ็ตรหัสผ่านเข้าสู่ระบบ"
        action_desc = "ระบบได้รับคำขอตั้งรหัสผ่านใหม่สำหรับบัญชี DiaBalance ของคุณ กรุณาใช้รหัส OTP ด้านล่างเพื่อดำเนินการต่อ:"
        security_note = "หากคุณไม่ได้ร้องขอการรีเซ็ตรหัสผ่าน โปรดเพิกเฉยต่ออีเมลฉบับนี้ รหัสผ่านเดิมของคุณยังคงปลอดภัย"
    else:
        # ค่าเริ่มต้นสำหรับสมัครสมาชิก (register)
        subject = "รหัส OTP ยืนยันการสมัครสมาชิก - DiaBalance"
        action_title = "ยืนยันการสมัครสมาชิกใหม่"
        action_desc = "ยินดีต้อนรับสู่ DiaBalance! กรุณานำรหัส OTP ด้านล่างไปกรอกบนหน้าเว็บไซต์เพื่อยืนยันตัวตนและเปิดใช้งานบัญชีของคุณ:"
        security_note = "หากคุณไม่ได้ทำการสมัครสมาชิกบนระบบ DiaBalance สามารถเพิกเฉยต่ออีเมลนี้ได้"

    # 1. ข้อความธรรมดา (Plain-text fallback เผื่อกรณีโปรแกรมอ่านอีเมลไม่รองรับ HTML)
    plain_text = f"""DiaBalance - {action_title}
--------------------------------------------------
{action_desc}

รหัส OTP ของคุณคือ: {otp_code}

* รหัสนี้มีอายุการใช้งาน 10 นาที
* {security_note}
* คำเตือน: ห้ามเปิดเผยรหัส OTP นี้แก่บุคคลอื่นโดยเด็ดขาด

เว็บไซต์: https://diabalance.tech
อีเมลฉบับนี้ส่งจากระบบอัตโนมัติ กรุณาอย่าตอบกลับ
"""

    # 2. ข้อความแบบ HTML ดีไซน์สวยงาม (Modern Healthcare Theme)
    html_text = f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Prompt', Tahoma, sans-serif; color: #334155;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; padding: 30px 10px;">
    <tr>
      <td align="center">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.06); border: 1px solid #e2e8f0;">
          
          <!-- Header แถบหัวเรื่อง DiaBalance -->
          <tr>
            <td style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); padding: 32px 24px; text-align: center; color: #ffffff;">
              <h1 style="margin: 0; font-size: 26px; font-weight: 800; letter-spacing: 1px;">DiaBalance</h1>
              <p style="margin: 6px 0 0 0; font-size: 13px; opacity: 0.92; font-weight: 400;">ระบบแนะนำการออกกำลังกายสำหรับผู้ป่วยเบาหวาน</p>
            </td>
          </tr>

          <!-- เนื้อหาหลัก (Content) -->
          <tr>
            <td style="padding: 32px 28px;">
              <!-- ป้าย Action Badge -->
              <div style="text-align: center; margin-bottom: 20px;">
                <span style="display: inline-block; background-color: #e0f2fe; color: #0284c7; padding: 6px 16px; border-radius: 9999px; font-size: 13px; font-weight: 700;">
                  {action_title}
                </span>
              </div>

              <!-- คำอธิบายบริบท -->
              <p style="margin: 0 0 24px 0; font-size: 15px; line-height: 1.6; color: #475569; text-align: center;">
                {action_desc}
              </p>

              <!-- กล่องแสดงรหัส OTP ขนาดใหญ่ -->
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 24px;">
                <tr>
                  <td style="background-color: #f8fafc; border: 2px dashed #0284c7; border-radius: 12px; padding: 22px 10px; text-align: center;">
                    <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.5px; color: #64748b; font-weight: 600; margin-bottom: 8px;">
                      รหัสยืนยันตัวตน (OTP)
                    </div>
                    <div style="font-family: 'SF Pro Text', Consolas, Monaco, monospace; font-size: 38px; font-weight: 800; letter-spacing: 8px; color: #0284c7; margin: 4px 0;">
                      {otp_code}
                    </div>
                    <div style="font-size: 13px; color: #dc2626; font-weight: 600; margin-top: 10px;">
                      ⏱️ รหัสมีอายุการใช้งาน 10 นาที
                    </div>
                  </td>
                </tr>
              </table>

              <!-- กล่องแจ้งเตือนความปลอดภัย -->
              <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; border-radius: 6px; font-size: 13px; color: #991b1b; line-height: 1.5;">
                <strong>ข้อควรระวัง:</strong> โปรดอย่าเปิดเผยรหัส OTP แก่บุคคลอื่น {security_note}
              </div>
            </td>
          </tr>

          <!-- Footer ด้านล่างสุด -->
          <tr>
            <td style="background-color: #f8fafc; padding: 22px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; line-height: 1.6;">
              <p style="margin: 0 0 6px 0;">อีเมลฉบับนี้ส่งจากระบบอัตโนมัติ กรุณาอย่าตอบกลับ</p>
              <p style="margin: 0 0 6px 0;">
                เข้าสู่เว็บไซต์: <a href="https://diabalance.tech" target="_blank" style="color: #0284c7; text-decoration: none; font-weight: 600;">diabalance.tech</a>
              </p>
              <p style="margin: 0;">&copy; 2026 DiaBalance. All rights reserved.</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return subject, plain_text, html_text


def send_otp_email(receiver_email, otp_code, action="register"):
    sender_email = os.getenv("sender_email")
    app_password = os.getenv("app_password")

    if not sender_email or not app_password:
        print("❌ Email Error: sender_email หรือ app_password ยังไม่ได้ตั้งค่าใน environment")
        return False

    # ตัดช่องว่างเผื่อผู้ใช้คัดลอกมาแบบมีเว้นวรรค
    app_password = app_password.replace(" ", "").strip()

    subject, plain_text, html_text = _generate_email_content(action, otp_code)

    # ใช้ MIMEMultipart("alternative") เพื่อแนบทั้ง Plain-text และ HTML
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = f"DiaBalance <{sender_email}>"
    msg["To"] = receiver_email

    # แนบ Plain-text ก่อน แล้วตามด้วย HTML (Email client จะแสดง HTML เป็นลำดับแรก)
    part1 = MIMEText(plain_text, "plain", "utf-8")
    part2 = MIMEText(html_text, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Email Error: {e}")
        return False