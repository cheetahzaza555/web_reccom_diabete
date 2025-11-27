# rules.py

# 1. แก้ตรงส่วนลบข้อมูลเก่า (DELETE)
DELETE_OLD_DATA = """
    PREFIX ex: <http://example.org/diabetes#>
    DELETE { 
        ?p ex:hasComorbidity ?c . 
        ?p ex:hasPatientWarning ?w . 
        ?p ex:recommendedExercise ?rec .  # <--- แก้ตรงนี้
    }
    WHERE { 
        ?p ex:hasComorbidity ?c . 
        OPTIONAL { ?p ex:hasPatientWarning ?w } . 
        OPTIONAL { ?p ex:recommendedExercise ?rec } # <--- แก้ตรงนี้
    }
"""

# กฎที่ 2: วินิจฉัย (Diagnosis)
# (คุณสามารถ copy กฎยาวๆ จากไฟล์เดิมมาวางตรงนี้ได้เลย)
RULE_DIAGNOSIS_NORMAL = """
    PREFIX ex: <http://example.org/diabetes#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    INSERT { 
        ?p ex:hasComorbidity ex:NoComorbidity . 
        ?p ex:hasPatientWarning ex:Warning1 . 
    }
    WHERE {
        ?p a ex:Patient ; ex:diabetType ex:T1DM ; ex:hasPhysicalExam ?pe .
        ?pe ex:hasBMI ?bmi .
        FILTER (xsd:decimal(?bmi) < 25.0)
    }
"""

# กฎที่ 3: แนะนำท่าออกกำลังกาย (Recommendation)
RULE_RECOMMENDATION = """
    PREFIX ex: <http://example.org/diabetes#>
    INSERT { ?p ex:recommendedExercise ?ex . } # <--- แก้ตรงนี้
    WHERE {
        ?p ex:hasComorbidity ex:NoComorbidity .
        ?ex a ex:Exercise .
    }
"""