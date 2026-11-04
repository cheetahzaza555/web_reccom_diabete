"""Validate health facts before saving or reasoning; missing is never normal."""
import math
import re
from datetime import date


class InvalidHealthData(ValueError):
    def __init__(self, fields):
        self.fields = fields
        super().__init__('กรุณาตรวจสอบข้อมูลก่อนรับคำแนะนำ: ' + ' / '.join(fields.values()))


def normalize_health_data(raw):
    if not isinstance(raw, dict):
        raise InvalidHealthData({'data': 'ข้อมูลต้องเป็นออบเจ็กต์ JSON'})
    data = dict(raw)
    errors = {}
    numeric = {
        'weight': ('น้ำหนัก', None), 'height': ('ส่วนสูง', None),
        'sbp': ('ความดันตัวบน', 'bp_high'), 'dbp': ('ความดันตัวล่าง', 'bp_low'),
        'chol': ('คอเลสเตอรอลรวม', 'cholesterol'), 'ldl': ('LDL', None),
        'hdl': ('HDL', None), 'tri': ('ไตรกลีเซอไรด์', 'triglyceride'),
        'fpg': ('น้ำตาลในเลือด FPG', None),
    }
    for key, (label, alias) in numeric.items():
        value = raw.get(key, raw.get(alias))
        try:
            if isinstance(value, bool):
                raise ValueError()
            value = float(value)
            if not math.isfinite(value) or value <= 0:
                raise ValueError()
            data[key] = value
        except (ValueError, TypeError, OverflowError):
            errors[key] = f'{label}: ต้องระบุตัวเลขที่มากกว่า 0'
    # Use measured height/weight, rather than trusting a client-supplied BMI.
    if 'weight' not in errors and 'height' not in errors:
        try:
            data['bmi'] = round(data['weight'] / (data['height'] / 100) ** 2, 2)
            if not math.isfinite(data['bmi']) or data['bmi'] <= 0:
                raise ValueError()
        except (ValueError, OverflowError, ZeroDivisionError):
            errors['height'] = 'กรุณาตรวจสอบน้ำหนักและส่วนสูง'

    diabetes_type = str(raw.get('type', '')).strip().upper()
    if diabetes_type not in {'T1DM', 'T2DM'}:
        errors['type'] = 'กรุณาระบุชนิดเบาหวาน'
    data['type'] = diabetes_type
    insulin = str(raw.get('insulin_use', '')).strip().lower()
    if insulin not in {'true', 'false'}:
        errors['insulin_use'] = 'กรุณาระบุการใช้อินซูลิน'
    data['insulin_use'] = insulin

    for key, label, alias in [('ketone', 'ผลตรวจคีโตน', None),
                              ('micro', 'ผลตรวจไมโครอัลบูมิน', 'microalbumin')]:
        value = str(raw.get(key, raw.get(alias, ''))).strip().lower()
        if value not in {'positive', 'negative'}:
            errors[key] = f'{label}: กรุณาระบุผลบวกหรือผลลบจากผลตรวจจริง'
        else:
            data[key] = value.capitalize()

    allowed = {v.lower(): v for v in ('Retinopathy', 'HeartDisease',
        'PeripheralNeuropathy', 'AutonomicNeuropathy', 'NoOtherComplication')}
    special = raw.get('special')
    if isinstance(special, str):
        special = [special]
    if (not isinstance(special, list) or not special or
            any(not isinstance(v, str) or v.strip().lower() not in allowed for v in special)):
        errors['special'] = 'กรุณาระบุภาวะแทรกซ้อนอื่น ๆ หรือยืนยันว่าไม่มีรายการที่ระบุ'
    else:
        data['special'] = list(dict.fromkeys(allowed[v.strip().lower()] for v in special))
        if 'NoOtherComplication' in data['special'] and len(data['special']) > 1:
            errors['special'] = 'ไม่สามารถเลือกไม่มีภาวะแทรกซ้อนพร้อมกับภาวะแทรกซ้อนได้'

    favorites = raw.get('favorites', [])
    if (not isinstance(favorites, list) or any(not isinstance(v, str) or
            not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', v) for v in favorites)):
        errors['favorites'] = 'รายการกิจกรรมที่ชอบไม่ถูกต้อง'
    if raw.get('frequency') and (not isinstance(raw['frequency'], str) or
            not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', raw['frequency'])):
        errors['frequency'] = 'รายการความถี่ไม่ถูกต้อง'

    for key, label in [('checkup_date', 'วันที่ตรวจร่างกาย'),
                       ('blood_test_date', 'วันที่ตรวจเลือด')]:
        try:
            value = date.fromisoformat(raw.get(key, ''))
            if value > date.today():
                raise ValueError()
            data[key] = value.isoformat()
        except (ValueError, TypeError):
            errors[key] = f'{label}: กรุณาระบุวันที่จริงที่ไม่ใช่วันในอนาคต'
    if errors:
        raise InvalidHealthData(errors)
    return data
