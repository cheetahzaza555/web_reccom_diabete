import cv2
import pytesseract
import numpy as np
import re

# ระบุ Path สำหรับ Windows (ถ้าใช้ Linux/Server ไม่ต้องมีบรรทัดนี้)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def process_ocr_image(image_file):
    """ฟังก์ชันหลักสำหรับรับไฟล์รูปและส่งกลับข้อมูลสุขภาพ"""
    # 1. แปลงไฟล์จาก Request เป็น OpenCV format
    img_array = np.frombuffer(image_file.read(), np.uint8)
    image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    # 2. Pre-processing (ทำให้ภาพชัดขึ้น)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 3. ใช้ Tesseract อ่านข้อความ
    text = pytesseract.image_to_string(thresh, lang='tha+eng')

    # 4. ใช้ RegEx ดึงข้อมูล
    data = {
        "hdl": re.search(r"HDL[:\s-]+(\d+\.?\d*)", text, re.I).group(1) if re.search(r"HDL[:\s-]+(\d+\.?\d*)", text, re.I) else "",
        "ldl": re.search(r"LDL[:\s-]+(\d+\.?\d*)", text, re.I).group(1) if re.search(r"LDL[:\s-]+(\d+\.?\d*)", text, re.I) else "",
        "cholesterol": re.search(r"(?:Cholesterol|CHOL)[:\s-]+(\d+\.?\d*)", text, re.I).group(1) if re.search(r"(?:Cholesterol|CHOL)[:\s-]+(\d+\.?\d*)", text, re.I) else "",
        "fpg": re.search(r"(?:FPG|Glucose|Sugar)[:\s-]+(\d+\.?\d*)", text, re.I).group(1) if re.search(r"(?:FPG|Glucose|Sugar)[:\s-]+(\d+\.?\d*)", text, re.I) else ""
    }
    return data