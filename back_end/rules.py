# rules.py - กฎทั้งหมดสำหรับระบบแนะนำการออกกำลังกาย

# ===== 1. ลบข้อมูลเก่าที่ถูกสร้างจากกฎ =====
DELETE_OLD_DATA = """
    PREFIX ex: <http://example.org/diabetes#>
    DELETE { 
        ?p ex:hasComorbidity ?c . 
        ?p ex:hasPatientWarning ?w . 
        ?p ex:recommendedExercise ?rec .
    }
    WHERE { 
        ?p a ex:Patient .
        OPTIONAL { ?p ex:hasComorbidity ?c } . 
        OPTIONAL { ?p ex:hasPatientWarning ?w } . # ❌ ลบส่วน . ?w ?wp ?wo ออกจากตรงนี้ด้วย
        OPTIONAL { ?p ex:recommendedExercise ?rec }
    }
"""

# ===== 2. กฎวินิจฉัย (Diagnosis Rules) =====

# กฎที่ 1: T1DM + BMI ปกติ → NoComorbidity + คำเตือนระดับ 1
RULE_DIAG_T1DM_NORMAL = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT { 
        ?p ex:hasComorbidity ex:NoComorbidity . 
        ?p ex:hasPatientWarning ex:Warning1 . 
    }
    WHERE {
        ?p a ex:Patient ; 
           ex:diabetType ex:T1DM ; 
           ex:hasPhysicalExam ?pe .
        ?pe ex:hasBMI ?bmi .
        FILTER (xsd:decimal(?bmi) < 25.0)
    }
"""

# กฎที่ 2: T1DM + BMI สูง → Obesity + คำเตือนระดับ 2
RULE_DIAG_T1DM_OBESITY = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT { 
        ?p ex:hasComorbidity ex:Obesity . 
        ?p ex:hasPatientWarning ex:Warning2 . 
    }
    WHERE {
        ?p a ex:Patient ; 
           ex:diabetType ex:T1DM ; 
           ex:hasPhysicalExam ?pe .
        ?pe ex:hasBMI ?bmi .
        FILTER (xsd:decimal(?bmi) >= 25.0)
    }
"""

# กฎที่ 3: T2DM + BMI ปกติ + ความดันปกติ → NoComorbidity
RULE_DIAG_T2DM_NORMAL = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT { 
        ?p ex:hasComorbidity ex:NoComorbidity . 
        ?p ex:hasPatientWarning ex:Warning2 . 
    }
    WHERE {
        ?p a ex:Patient ; 
           ex:diabetType ex:T2DM ; 
           ex:hasPhysicalExam ?pe .
        ?pe ex:hasBMI ?bmi ;
            ex:hasSBP ?sbp ;
            ex:hasDBP ?dbp .
        FILTER (xsd:decimal(?bmi) < 25.0 && 
                xsd:decimal(?sbp) < 130.0 && 
                xsd:decimal(?dbp) < 85.0)
    }
"""

# กฎที่ 4: T2DM + ความดันสูง → Hypertension
RULE_DIAG_T2DM_HT = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT { 
        ?p ex:hasComorbidity ex:Hypertension . 
        ?p ex:hasPatientWarning ex:Warning3 . 
    }
    WHERE {
        ?p a ex:Patient ; 
           ex:diabetType ex:T2DM ; 
           ex:hasPhysicalExam ?pe .
        ?pe ex:hasSBP ?sbp ;
            ex:hasDBP ?dbp .
        FILTER (xsd:decimal(?sbp) >= 130.0 || xsd:decimal(?dbp) >= 85.0)
    }
"""

# กฎที่ 5: T2DM + ไขมันสูง → Dyslipidemia
RULE_DIAG_T2DM_DYSLIP = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT { 
        ?p ex:hasComorbidity ex:Dyslipidemia . 
        ?p ex:hasPatientWarning ex:Warning4 . 
    }
    WHERE {
        ?p a ex:Patient ; 
           ex:diabetType ex:T2DM ; 
           ex:hasLabExam ?le .
        ?le ex:hasTotalCholesterol ?chol ;
            ex:hasLDL ?ldl .
        FILTER (xsd:decimal(?chol) >= 200.0 || xsd:decimal(?ldl) >= 130.0)
    }
"""

# กฎที่ 6: T2DM + BMI สูง → Obesity
RULE_DIAG_T2DM_OBESITY = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT { 
        ?p ex:hasComorbidity ex:Obesity . 
        ?p ex:hasPatientWarning ex:Warning5 . 
    }
    WHERE {
        ?p a ex:Patient ; 
           ex:diabetType ex:T2DM ; 
           ex:hasPhysicalExam ?pe .
        ?pe ex:hasBMI ?bmi .
        FILTER (xsd:decimal(?bmi) >= 30.0)
    }
"""

# รวมกฎวินิจฉัยทั้งหมด
DIAGNOSIS_RULES = [
    RULE_DIAG_T1DM_NORMAL,
    RULE_DIAG_T1DM_OBESITY,
    RULE_DIAG_T2DM_NORMAL,
    RULE_DIAG_T2DM_HT,
    RULE_DIAG_T2DM_DYSLIP,
    RULE_DIAG_T2DM_OBESITY
]

# ===== 3. กฎแนะนำท่าออกกำลังกาย (Recommendation Rules) =====

# กฎที่ 1: NoComorbidity → แนะนำทุกท่า
RULE_REC_NO_COMORBIDITY = """
    PREFIX ex: <http://example.org/diabetes#>
    INSERT { ?p ex:recommendedExercise ?ex . }
    WHERE {
        ?p ex:hasComorbidity ex:NoComorbidity .
        ?ex a ex:Exercise .
    }
"""

# กฎที่ 2: Obesity → แนะนำท่าที่เหมาะสมสำหรับคนอ้วน
RULE_REC_OBESITY = """
    PREFIX ex: <http://example.org/diabetes#>
    INSERT { ?p ex:recommendedExercise ?ex . }
    WHERE {
        ?p ex:hasComorbidity ex:Obesity .
        ?ex a ex:Exercise ;
            ex:suitableForObesity "true"^^xsd:boolean .
    }
"""

# กฎที่ 3: Hypertension → แนะนำท่าที่ไม่เสี่ยงต่อความดันสูง
RULE_REC_HYPERTENSION = """
    PREFIX ex: <http://example.org/diabetes#>
    INSERT { ?p ex:recommendedExercise ?ex . }
    WHERE {
        ?p ex:hasComorbidity ex:Hypertension .
        ?ex a ex:Exercise ;
            ex:suitableForHypertension "true"^^xsd:boolean .
    }
"""

# กฎที่ 4: Dyslipidemia → แนะนำท่าที่ช่วยเผาผลาญไขมัน
RULE_REC_DYSLIPIDEMIA = """
    PREFIX ex: <http://example.org/diabetes#>
    INSERT { ?p ex:recommendedExercise ?ex . }
    WHERE {
        ?p ex:hasComorbidity ex:Dyslipidemia .
        ?ex a ex:Exercise ;
            ex:suitableForDyslipidemia "true"^^xsd:boolean .
    }
"""

# รวมกฎแนะนำทั้งหมด
RECOMMENDATION_RULES = [
    RULE_REC_NO_COMORBIDITY,
    RULE_REC_OBESITY,
    RULE_REC_HYPERTENSION,
    RULE_REC_DYSLIPIDEMIA
]