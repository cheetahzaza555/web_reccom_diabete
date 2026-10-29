# modules/db/auth_repository.py
"""
ฟังก์ชันจัดการระบบสมาชิก: สมัครสมาชิก, เข้าสู่ระบบ, จัดการโปรไฟล์และรหัสผ่าน
"""

import uuid
import datetime
from .connection import sparql_read, sparql_write, escape_sparql


def is_username_taken(username):
    if not username:
        return False
    check_query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    ASK {{ ?p ex:username "{escape_sparql(username)}" . }}
    """
    try:
        sparql_read.setQuery(check_query)
        return bool(sparql_read.query().convert().get("boolean", False))
    except Exception as e:
        print(f"Error checking username: {e}")
        return False


def register_new_patient(username, password_hash, firstname, lastname, email, role="user", auth_provider="local"):
    if not username or not password_hash:
        return {"success": False, "message": "ข้อมูลไม่ครบถ้วน"}

    new_id = str(uuid.uuid4())[:8]
    pid = f"Patient{new_id}"
    created_at = datetime.datetime.now().isoformat()

    try:
        if is_username_taken(username):
            return {"success": False, "message": "Username นี้มีผู้ใช้งานแล้ว"}

        insert_query = f"""
        PREFIX ex: <http://example.org/diabetes#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        INSERT DATA {{
            ex:{pid} a ex:Patient ;
                     ex:username "{escape_sparql(username)}" ;
                     ex:passwordHash "{escape_sparql(password_hash)}" ;
                     ex:firstname "{escape_sparql(firstname)}" ;
                     ex:lastname "{escape_sparql(lastname)}" ;
                     ex:email "{escape_sparql(email)}" ;
                     ex:role "{escape_sparql(role)}" ;
                     ex:authProvider "{escape_sparql(auth_provider)}" ;
                     ex:createdAt "{created_at}"^^xsd:dateTime .
        }}
        """
        sparql_write.setQuery(insert_query)
        sparql_write.query()
        return {"success": True, "patient_id": pid}
    except Exception as e:
        return {"success": False, "message": str(e)}


def get_user_for_login(username):
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?patient ?passwordHash ?role ?fname ?lname ?email ?authProvider
    WHERE {{
        ?patient a ex:Patient .
        ?patient ex:username "{escape_sparql(username)}" .
        ?patient ex:passwordHash ?passwordHash .
        OPTIONAL {{ ?patient ex:role ?role }}
        OPTIONAL {{ ?patient ex:firstname ?fname }}
        OPTIONAL {{ ?patient ex:lastname ?lname }}
        OPTIONAL {{ ?patient ex:email ?email }}
        OPTIONAL {{ ?patient ex:authProvider ?authProvider }}
    }} LIMIT 1
    """
    try:
        sparql_read.setQuery(query)
        bindings = sparql_read.query().convert()["results"]["bindings"]
        if not bindings:
            return None

        r = bindings[0]
        full_uri = r["patient"]["value"]
        pid = full_uri.split("#Patient")[-1]

        return {
            "patient_id": pid,
            "username": username,
            "password_hash": r["passwordHash"]["value"],
            "role": r.get("role", {}).get("value", "user"),
            "firstname": r.get("fname", {}).get("value", ""),
            "lastname": r.get("lname", {}).get("value", ""),
            "email": r.get("email", {}).get("value", ""),
            "auth_provider": r.get("authProvider", {}).get("value", "local")
        }
    except Exception as e:
        print(f"Error login: {e}")
        return None


def get_user_by_id(user_id):
    clean_id = str(user_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?username ?role ?fname ?lname ?email ?authProvider
    WHERE {{
        ex:{pid} a ex:Patient .
        OPTIONAL {{ ex:{pid} ex:username ?username }}
        OPTIONAL {{ ex:{pid} ex:role ?role }}
        OPTIONAL {{ ex:{pid} ex:firstname ?fname }}
        OPTIONAL {{ ex:{pid} ex:lastname ?lname }}
        OPTIONAL {{ ex:{pid} ex:email ?email }}
        OPTIONAL {{ ex:{pid} ex:authProvider ?authProvider }}
    }} LIMIT 1
    """
    try:
        sparql_read.setQuery(query)
        res = sparql_read.query().convert()
        bindings = res["results"]["bindings"]
        if not bindings:
            return None

        r = bindings[0]
        return {
            "id": user_id,
            "username": r.get("username", {}).get("value", ""),
            "role": r.get("role", {}).get("value", "user"),
            "firstname": r.get("fname", {}).get("value", ""),
            "lastname": r.get("lname", {}).get("value", ""),
            "email": r.get("email", {}).get("value", ""),
            "auth_provider": r.get("authProvider", {}).get("value", "local")
        }
    except Exception as e:
        print(f"Error in get_user_by_id: {e}")
        return None


def get_password_hash_by_id(user_id):
    clean_id = str(user_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?hash WHERE {{ ex:{pid} ex:passwordHash ?hash . }} LIMIT 1
    """
    try:
        sparql_read.setQuery(query)
        res = sparql_read.query().convert()
        bindings = res["results"]["bindings"]
        if bindings:
            return bindings[0]["hash"]["value"]
        return None
    except Exception as e:
        print(f"Error getting password hash: {e}")
        return None


def update_user_profile_db(user_id, firstname, lastname, new_hash=None):
    clean_id = str(user_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"

    delete_pass = f"ex:{pid} ex:passwordHash ?oldHash ." if new_hash else ""
    insert_pass = f'ex:{pid} ex:passwordHash "{escape_sparql(new_hash)}" .' if new_hash else ""
    where_pass = f"OPTIONAL {{ ex:{pid} ex:passwordHash ?oldHash }}" if new_hash else ""

    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    DELETE {{
        ex:{pid} ex:firstname ?oldF .
        ex:{pid} ex:lastname ?oldL .
        {delete_pass}
    }}
    INSERT {{
        ex:{pid} ex:firstname "{escape_sparql(firstname)}" .
        ex:{pid} ex:lastname "{escape_sparql(lastname)}" .
        {insert_pass}
    }}
    WHERE {{
        ex:{pid} a ex:Patient .
        OPTIONAL {{ ex:{pid} ex:firstname ?oldF }}
        OPTIONAL {{ ex:{pid} ex:lastname ?oldL }}
        {where_pass}
    }}
    """
    try:
        sparql_write.setQuery(query)
        sparql_write.query()
        return True
    except Exception as e:
        print(f"❌ Error updating profile: {e}")
        return False


def update_password_db(patient_id, new_password_hash):
    clean_id = str(patient_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    DELETE {{
        ?patient ex:passwordHash ?oldHash .
    }}
    INSERT {{
        ?patient ex:passwordHash "{escape_sparql(new_password_hash)}" .
    }}
    WHERE {{
        BIND(ex:{pid} AS ?patient)
        OPTIONAL {{ ?patient ex:passwordHash ?oldHash . }}
    }}
    """
    try:
        sparql_write.setQuery(query)
        sparql_write.query()
        return True
    except Exception as e:
        print(f"❌ Error updating password: {e}")
        return False


def get_user_by_email(email):
    """ค้นหาข้อมูลผู้ใช้งานจากอีเมล"""
    if not email:
        return None
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    SELECT ?patient ?username ?passwordHash ?role ?fname ?lname ?email ?authProvider
    WHERE {{
        ?patient a ex:Patient .
        ?patient ex:email "{escape_sparql(email)}" .
        OPTIONAL {{ ?patient ex:username ?username }}
        OPTIONAL {{ ?patient ex:passwordHash ?passwordHash }}
        OPTIONAL {{ ?patient ex:role ?role }}
        OPTIONAL {{ ?patient ex:firstname ?fname }}
        OPTIONAL {{ ?patient ex:lastname ?lname }}
        OPTIONAL {{ ?patient ex:authProvider ?authProvider }}
    }} LIMIT 1
    """
    try:
        sparql_read.setQuery(query)
        bindings = sparql_read.query().convert()["results"]["bindings"]
        if not bindings:
            return None

        r = bindings[0]
        full_uri = r["patient"]["value"]
        pid = full_uri.split("#Patient")[-1]

        return {
            "patient_id": pid,
            "username": r.get("username", {}).get("value", ""),
            "password_hash": r.get("passwordHash", {}).get("value", ""),
            "role": r.get("role", {}).get("value", "user"),
            "firstname": r.get("fname", {}).get("value", ""),
            "lastname": r.get("lname", {}).get("value", ""),
            "email": email,
            "auth_provider": r.get("authProvider", {}).get("value", "local")
        }
    except Exception as e:
        print(f"Error getting user by email: {e}")
        return None


def set_user_auth_provider(patient_id, provider="google"):
    """อัปเดตหรือกำหนดประเภท Provider (เช่น google, local) ให้กับบัญชีผู้ใช้"""
    clean_id = str(patient_id).replace("Patient", "").replace("SUPA", "")
    pid = f"Patient{clean_id}"
    query = f"""
    PREFIX ex: <http://example.org/diabetes#>
    DELETE {{
        ex:{pid} ex:authProvider ?oldProvider .
    }}
    INSERT {{
        ex:{pid} ex:authProvider "{escape_sparql(provider)}" .
    }}
    WHERE {{
        ex:{pid} a ex:Patient .
        OPTIONAL {{ ex:{pid} ex:authProvider ?oldProvider . }}
    }}
    """
    try:
        sparql_write.setQuery(query)
        sparql_write.query()
        return True
    except Exception as e:
        print(f"Error setting auth provider: {e}")
        return False


def register_google_user(email, firstname="", lastname=""):
    """สร้างบัญชีผู้ใช้งานใหม่จากข้อมูล Google OAuth"""
    if not email:
        return {"success": False, "message": "ข้อมูลอีเมลไม่ถูกต้อง"}

    base_username = email.split("@")[0].replace(".", "_")
    username = base_username
    counter = 1
    while is_username_taken(username):
        username = f"{base_username}_{counter}"
        counter += 1

    from werkzeug.security import generate_password_hash
    import secrets
    random_password = secrets.token_urlsafe(16)
    password_hash = generate_password_hash(random_password)

    return register_new_patient(
        username=username,
        password_hash=password_hash,
        firstname=firstname or "",
        lastname=lastname or "",
        email=email,
        role="user",
        auth_provider="google"
    )
