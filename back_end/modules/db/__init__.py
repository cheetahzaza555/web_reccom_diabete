# modules/db/__init__.py
"""
รวม import จากทุกไฟล์ใน modules/db/ ไว้ที่เดียว
เพื่อให้ไฟล์อื่นในโปรเจค (routes/, modules/logic.py ฯลฯ) 
เรียกใช้ได้เหมือนเดิมโดยไม่ต้องแก้โค้ด import ที่มีอยู่แล้ว

ตัวอย่าง: จากเดิม
    from modules.database import get_patient_profile
เปลี่ยนเป็นแค่
    from modules.db import get_patient_profile
"""

from .connection import (
    sparql_read,
    sparql_write,
    validate_id,
    escape_sparql,
    safe_float,
    get_thai_text,
    safe_get_name,
)

from .patient_repository import (
    save_raw_patient_data,
    save_results_to_db,
    delete_patient,
    get_patient_profile,
    get_patient_latest_record,
)

from .exercise_repository import (
    get_all_recommendations,
    get_exercise_details_by_id,
    get_all_exercises_for_library,
    get_exercise_by_id,
)

from .auth_repository import (
    register_new_patient,
    get_user_for_login,
    get_user_by_id,
    get_password_hash_by_id,
    update_user_profile_db,
    update_password_db,
)

from .plan_repository import (
    generate_30_days_plan,
    get_dashboard_schedule,
    delete_user_schedule,
    update_daily_plan_status,
    get_daily_plan_info,
)

from .admin_repository import (
    get_admin_dashboard_stats,
    get_recent_registered_users,
    get_patient_health_summary,
    get_all_users_with_roles,
    update_user_role_in_graphdb,
)