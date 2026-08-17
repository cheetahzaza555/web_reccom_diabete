import os
import json
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def process_ocr_image(image_file):
    
    """
    ฟังก์ชันส่งรูปภาพใบแล็บไปให้ Gemini API วิเคราะห์ 
    และสั่งให้ส่งผลลัพธ์กลับมาเป็น JSON โครงสร้างตรงตามที่ระบบต้องการ
    """
    try:
        # 1. เช็กและดึง API Key ให้ชัวร์ก่อนเริ่มทำงาน
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("ไม่พบ GEMINI_API_KEY ในไฟล์ .env")

        # 2. สร้าง Client ภายในฟังก์ชันพร้อมลบช่องว่างส่วนเกิน (.strip())
        client = genai.Client(api_key=api_key.strip())

        # 3. เตรียมไฟล์ภาพ
        image_file.seek(0)
        image = Image.open(image_file)

        # 4. ออกแบบ Prompt
        prompt = """
        You are an expert medical data extraction assistant. 
        Analyze the provided health checkup or blood test report image and extract the following parameters.
        
        Strict Guidelines:
        1. Extract numbers only as a string (e.g., "62.8", "120", "211").
        2. For Blood Pressure (bp), combine systolic and diastolic into "systolic/diastolic" format (e.g., "113/51"). If you find separate values, combine them.
        3. For Date (date), format it as "DD/MM/YYYY" (e.g., "04/07/2026").
        4. If any value is missing or completely unreadable from the image, return it as an empty string "".
        5. Do not guess or hallucinate data that does not exist in the image.
        """

        # 5. กำหนด Schema
        json_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "date": types.Schema(type=types.Type.STRING, description="Date of checkup in DD/MM/YYYY format"),
                "weight": types.Schema(type=types.Type.STRING, description="Weight in kg"),
                "height": types.Schema(type=types.Type.STRING, description="Height in cm"),
                "bmi": types.Schema(type=types.Type.STRING, description="Body Mass Index"),
                "bp": types.Schema(type=types.Type.STRING, description="Blood Pressure in systolic/diastolic format"),
                "fpg": types.Schema(type=types.Type.STRING, description="Fasting Blood Glucose / Sugar"),
                "hdl": types.Schema(type=types.Type.STRING, description="HDL Cholesterol"),
                "ldl": types.Schema(type=types.Type.STRING, description="LDL Cholesterol"),
                "cholesterol": types.Schema(type=types.Type.STRING, description="Total Cholesterol"),
                "triglyceride": types.Schema(type=types.Type.STRING, description="Triglyceride"),
            },
            required=["date", "weight", "height", "bmi", "bp", "fpg", "hdl", "ldl", "cholesterol", "triglyceride"]
        )

        print("🤖 [GEMINI LOG] กำลังส่งรูปภาพไปให้ Gemini ประมวลผล...")

        # 6. เรียกใช้ Gemini API (แนะนำ gemini-2.5-flash หรือ gemini-1.5-flash)
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=json_schema,
                temperature=0.1
            ),
        )

        # 7. แปลงผลลัพธ์เป็น Dictionary
        data = json.loads(response.text)
        print(f"📊 [GEMINI LOG] สกัดข้อมูลสำเร็จด้วย AI: {data}\n")
        return data

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในระบบ Gemini OCR: {str(e)}")
        return {
            "date": "", "weight": "", "height": "", "bmi": "", "bp": "",
            "hdl": "", "ldl": "", "cholesterol": "", "fpg": "", "triglyceride": ""
        }