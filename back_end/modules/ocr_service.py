import os
import json
import threading
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

_client = None
_client_lock = threading.Lock()
_ocr_slots = threading.BoundedSemaphore(
    max(1, int(os.getenv("OCR_MAX_CONCURRENT", "4")))
)


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError("ไม่พบ GEMINI_API_KEY ในไฟล์ .env")
                _client = genai.Client(api_key=api_key.strip())
    return _client


def _prepare_image(image_file):
    image_file.seek(0)
    image = Image.open(image_file)
    image.load()

    # Keep OCR details while limiting upload size and API processing time.
    image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    return image

def process_ocr_image(image_file):
    
    """
    ฟังก์ชันส่งรูปภาพใบแล็บไปให้ Gemini API วิเคราะห์ 
    และสั่งให้ส่งผลลัพธ์กลับมาเป็น JSON โครงสร้างตรงตามที่ระบบต้องการ
    """
    try:
        client = _get_client()
        image = _prepare_image(image_file)

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

        # Limit concurrent upstream calls so traffic spikes do not exhaust workers/API quota.
        with _ocr_slots:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
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