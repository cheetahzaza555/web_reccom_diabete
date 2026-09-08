# modules/ontology.py
import io
import requests
from owlready2 import *
from modules.config import GRAPHDB_READ, REPO_NAME

def load_ontology():
    print(f"🌍 Loading Ontology from {REPO_NAME}...")
    headers = {"Accept": "text/plain"} 
    params = {"infer": "false"} 
    try:
        response = requests.get(f"{GRAPHDB_READ}/statements", headers=headers, params=params)
        response.raise_for_status()
        raw_data = response.content.decode('utf-8')
        # ✅ [FIX] กรองทั้ง owl:imports และ "X a owl:Ontology" ทิ้ง
        # เพราะ entity ที่ถูกประกาศเป็น owl:Ontology ซ้อนอยู่ใต้ namespace หลัก
        # (เช่น ex:exerciseInst a owl:Ontology — เศษที่หลงเหลือจากการ import ไฟล์
        # ในเครื่อง local ผ่าน Protégé) ทำให้ owlready2 สร้าง sub-ontology แยก
        # แล้วเอา individual ใหม่ที่สร้างผ่าน ex.PhysicalExam(...)/ex.Patient(...) ไป
        # ผูกกับ sub-ontology ปลอมนั้นแทน (เช่น .../diabetes#exerciseInst#hasWeight)
        # ทำให้กฎ SWRL ทั้งหมด (ที่อ้างอิง .../diabetes#hasWeight ตรงๆ) ไม่ match เลย
        clean_lines = [
            line for line in raw_data.splitlines()
            if "http://www.w3.org/2002/07/owl#imports" not in line
            and "http://www.w3.org/2002/07/owl#Ontology" not in line
        ]
        clean_data = "\n".join(clean_lines)

        # ✅ [FIX] เดิมใช้ base IRI "http://example.org/diabetes_from_db" ซึ่งไม่ตรงกับ
        # namespace จริงที่ข้อมูล/กฎ SWRL ทั้งหมดใช้ ("http://example.org/diabetes#")
        # ทำให้ owlready2 มองว่า entity ใหม่ที่สร้างผ่าน ex.Patient(...)/ex.PhysicalExam(...)
        # (ใน logic.py) อยู่คนละ ontology-graph กับกฎ/entity เดิมที่โหลดมาจาก GraphDB
        # (เห็นได้จาก repr ตอน debug: "diabetes_from_db.PE_xxx" vs "diabetes.T2DM")
        # แก้โดยให้ base IRI ตรงกับ namespace จริง เพื่อให้ entity ใหม่ถูกผูกกับ
        # ontology graph เดียวกับกฎทั้งหมด แล้ว sync_reasoner_pellet ถึงจะเห็นทุกอย่างครบ
        onto = get_ontology("http://example.org/diabetes#").load(fileobj=io.BytesIO(clean_data.encode('utf-8')), format="ntriples")

        print(f"✅ Loaded! Rules count: {len(list(onto.rules()))}")
        return onto
    except Exception as e:
        print(f"❌ Error loading ontology: {e}")
        return None

onto = load_ontology()

# ประกาศ Namespaces และ Classes
if onto:
    ex = onto.get_namespace("http://example.org/diabetes#")
    with onto:
        class Patient(Thing): namespace = ex
        class PhysicalExam(Thing): namespace = ex
        class LabExam(Thing): namespace = ex
        class Exercise(Thing): namespace = ex
        class DiabetType(Thing): namespace = ex
        class PatientWarning(Thing): namespace = ex
        class Comorbidity(Thing): namespace = ex 
        class Complication(Thing): namespace = ex 
        
        class hasBMI(DataProperty): namespace = ex; range = [float]
        class hasSBP(DataProperty): namespace = ex; range = [float]
        class hasDBP(DataProperty): namespace = ex; range = [float]
        class hasTotalCholesterol(DataProperty): namespace = ex; range = [float]
        class hasLDL(DataProperty): namespace = ex; range = [float]
        class hasHDL(DataProperty): namespace = ex; range = [float]
        class hasTriglyceride(DataProperty): namespace = ex; range = [float]
        class hasFPG(DataProperty): namespace = ex; range = [float]
        class hasWeight(DataProperty): namespace = ex; range = [float]
        class hasHeight(DataProperty): namespace = ex; range = [float]
        
        class hasKetone(DataProperty): namespace = ex; range = [str]
        class hasMicroalbuminurin(DataProperty): namespace = ex; range = [str]
        
        class diabetType(ObjectProperty): namespace = ex; range = [DiabetType]
        class hasPhysicalExam(ObjectProperty): namespace = ex; range = [PhysicalExam]
        class hasLabExam(ObjectProperty): namespace = ex; range = [LabExam]
        class recommendedExercise(ObjectProperty): namespace = ex; range = [Exercise]
        class hasPatientWarning(ObjectProperty): namespace = ex; range = [PatientWarning]
        class hasComorbidity(ObjectProperty): namespace = ex; range = [Comorbidity]
        class hasComplication(ObjectProperty): namespace = ex; range = [Complication]
        class hasSpecialComplication(ObjectProperty): namespace = ex; range = [Complication]
        
        class intensityOfExercise(ObjectProperty): namespace = ex
        class exerciseFrequency(ObjectProperty): namespace = ex
else:
    print("⚠️ Ontology failed to load. 'ex' namespace set to None — recommendation features will be disabled.")
    ex = None