import os
import io
import json
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
# 🔑 ตั้งค่า API Key (แนะนำให้ตั้งใน Environment Variable หรือวางตรงๆ สำหรับทดสอบ)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def process_ocr_image(image_file):
    """
    ฟังก์ชันส่งรูปภาพใบแล็บไปให้ Gemini API วิเคราะห์ 
    และสั่งให้ส่งผลลัพธ์กลับมาเป็น JSON โครงสร้างตรงตามที่ระบบต้องการ
    """
    try:
        # รีเซ็ตตำแหน่ง pointer ของไฟล์ภาพ
        image_file.seek(0)
        
        # 1. แปลงไฟล์จาก Request เป็น PIL Image (สำหรับส่งให้ Gemini)
        image = Image.open(image_file)

        # 2. ออกแบบ Prompt (คำสั่ง) ควบคุมพฤติกรรมและการบังคับให้ส่งข้อมูลกลับเป็น JSON
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

        # 3. กำหนดโครงสร้าง JSON (Schema) บังคับผลลัพธ์ให้ตรงกับที่หน้าบ้านต้องการร้อยเปอร์เซ็นต์
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

        print("🤖 [GEMINI LOG] กำลังส่งรูปภาพไปให้ Gemini 2.5 Flash ประมวลผล...")

        # 4. เรียกใช้บริการ Gemini API
        response = client.models.generate_content(
            model='gemini-2.5-flash', # โมเดลเริ่มต้นที่มี Vision และทำงานเร็วมาก
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", # บังคับปลายทางตอบกลับเป็น JSON แท้
                response_schema=json_schema,
                temperature=0.1 # ตั้งค่าต่ำเพื่อให้ผลลัพธ์แม่นยำตามข้อเท็จจริง ไม่มโนค่าขึ้นมาเอง
            ),
        )

        # 5. แปลงข้อความ JSON String จาก Gemini ออกมาเป็น Python Dictionary
        result_text = response.text
        data = json.loads(result_text)
        
        print(f"📊 [GEMINI LOG] สกัดข้อมูลสำเร็จด้วย AI: {data}\n")
        return data

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในระบบ Gemini OCR: {str(e)}")
        # หากเกิดปัญหาโครงสร้างพัง ให้ส่งโครงสร้างเปล่ากลับไป หน้าบ้านจะได้ไม่แครช
        return {
            "date": "", "weight": "", "height": "", "bmi": "", "bp": "",
            "hdl": "", "ldl": "", "cholesterol": "", "fpg": "", "triglyceride": ""
        }