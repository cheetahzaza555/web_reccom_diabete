import cv2
import pytesseract
import numpy as np
import re

# ระบุ Path สำหรับ Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def process_ocr_image(image_file):
    """ฟังก์ชันหลักสำหรับรับไฟล์รูปและส่งกลับข้อมูลสุขภาพ"""
    try:
        # รีเซ็ตตำแหน่ง pointer ของไฟล์ภาพให้อยู่จุดเริ่มต้น (ป้องกันกรณีไฟล์ถูกอ่านไปก่อนหน้า)
        image_file.seek(0)
        
        # 1. แปลงไฟล์จาก Request เป็น OpenCV format
        img_array = np.frombuffer(image_file.read(), np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        # ดักเช็ก: ถ้าแกะภาพไม่ได้ให้แสดง Error ทันที
        if image is None:
            print("❌ Error: ไม่สามารถแปลงไฟล์เป็นรูปภาพได้ ภาพอาจจะเสียหรือส่งมาผิดรูปแบบ")
            return {"hdl": "", "ldl": "", "cholesterol": "", "fpg": ""}

        # 2. Pre-processing (ทำให้ภาพชัดขึ้น)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 3. ใช้ Tesseract อ่านข้อความ (รองรับ ไทย + อังกฤษ)
        text = pytesseract.image_to_string(thresh, lang='tha+eng')

        # 🔍 บังคับพิมพ์ข้อความดิบออกหน้าจอหลังบ้าน (Terminal) เพื่อตรวจดูว่า AI เห็นคำว่าอะไรบ้าง
        print("\n=== [DEBUG LOG] ข้อความดิบที่ AI สแกนได้จากรูป ===")
        print(text if text.strip() else "(...ภาพว่างเปล่า ไม่มีตัวอักษร...)")
        print("===============================================\n")

        data = {
            "hdl": re.search(r"HDL[:\s-]+(\d+\.?\d*)", text, re.I).group(1) if re.search(r"HDL[:\s-]+(\d+\.?\d*)", text, re.I) else "",
            "ldl": re.search(r"LDL[:\s-]+(\d+\.?\d*)", text, re.I).group(1) if re.search(r"LDL[:\s-]+(\d+\.?\d*)", text, re.I) else "",
            "cholesterol": re.search(r"(?:Cholesterol|CHOL)[:\s-]+(\d+\.?\d*)", text, re.I).group(1) if re.search(r"(?:Cholesterol|CHOL)[:\s-]+(\d+\.?\d*)", text, re.I) else "",
            "fpg": re.search(r"(?:FPG|Glucose|Sugar)[:\s-]+(\d+\.?\d*)", text, re.I).group(1) if re.search(r"(?:FPG|Glucose|Sugar)[:\s-]+(\d+\.?\d*)", text, re.I) else ""
        }
        
        print(f"📊 [DEBUG LOG] ข้อมูลสุขภาพที่ดึงได้สำเร็จ: {data}\n")
        return data

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในระบบ OCR: {str(e)}")
        return {"hdl": "", "ldl": "", "cholesterol": "", "fpg": ""}