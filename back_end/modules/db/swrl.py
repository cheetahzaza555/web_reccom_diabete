import re
from SPARQLWrapper import SPARQLWrapper, JSON , POST
from modules.config import GRAPHDB_READ, GRAPHDB_WRITE
import uuid

def get_all_swrl_rules():
    """ฟังก์ชันดึงรายชื่อและรายละเอียดกฎ SWRL ฉบับเต็มแบบครบถ้วนทุก Atom"""
    sparql_read_client = SPARQLWrapper(GRAPHDB_READ)
    
    # 🟢 SPARQL Query ใหม่: แกะแยกประเภท Atom ชัดเจน 100% ไม่ให้ Property หาย
    query = """
    PREFIX swrl: <http://www.w3.org/2003/11/swrl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX swrla: <http://swrl.stanford.edu/ontologies/3.3/swrla.owl#>
    PREFIX ex: <http://example.org/diabetes#>

    SELECT DISTINCT ?ruleURI ?ruleLabel ?comment ?isEnabled ?part ?atom ?atomType ?pred ?arg1 ?arg2 ?builtin ?builtinArg1 ?builtinArg2 WHERE {
        ?ruleURI a swrl:Imp .
        
        OPTIONAL { ?ruleURI rdfs:label ?ruleLabel . }
        OPTIONAL { ?ruleURI rdfs:comment ?comment . }
        OPTIONAL { ?ruleURI swrla:isRuleEnabled ?isEnabled . }
        
        {
            ?ruleURI swrl:body ?list .
            BIND("body" AS ?part)
        } UNION {
            ?ruleURI swrl:head ?list .
            BIND("head" AS ?part)
        }
        
        ?list rdf:rest*/rdf:first ?atom .
        ?atom a ?atomType .
        
        # ดึงรายละเอียดตามประเภทของ Atom
        {
            # 1. Class Atom -> e.g. Patient(?x)
            ?atom swrl:classPredicate ?pred . 
            ?atom swrl:argument1 ?arg1 . 
        } UNION {
            # 2. Individual Property Atom -> e.g. hasSBP(?pe, ?sbp), hasLabExam(?x, ?le)
            ?atom swrl:propertyPredicate ?pred . 
            ?atom swrl:argument1 ?arg1 . 
            ?atom swrl:argument2 ?arg2 . 
        } UNION {
            # 3. Datavalued Property Atom (สำหรับบาง Property ที่เก็บเป็น DataProperty)
            ?atom swrl:propertyPredicate ?pred . 
            ?atom swrl:argument1 ?arg1 . 
            ?atom swrl:argument2 ?arg2 . 
        } UNION {
            # 4. Builtin Atom -> e.g. swrlb:lessThan(?sbp, 140)
            ?atom swrl:builtin ?builtin .
            ?atom swrl:arguments ?argsList .
            ?argsList rdf:first ?builtinArg1 .
            OPTIONAL {
                ?argsList rdf:rest ?argsRest .
                ?argsRest rdf:first ?builtinArg2 .
            }
        }
    }
    """
    
    try:
        sparql_read_client.setQuery(query)
        sparql_read_client.setReturnFormat(JSON)
        results = sparql_read_client.query().convert()
        
        rules_dict = {}
        
        def clean_uri(val):
            if not val: return ""
            return (val.replace("http://example.org/diabetes#", "ex:")
                       .replace("http://example.org/", "ex:")
                       .replace("http://www.w3.org/2003/11/swrlb#", "swrlb:")
                       .replace("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:"))

        def format_arg(arg_str):
            if not arg_str:
                return ""
            
            # SWRL Variable
            if "urn:swrl:var#" in arg_str:
                return "?" + arg_str.split("#")[-1]
            elif "http://www.w3.org/2003/11/swrl#" in arg_str:
                return "?" + arg_str.split("#")[-1]
            elif arg_str.startswith("urn:"):
                return "?" + arg_str.split(":")[-1]
            
            # Anonymous / Named Variable ใน Ontology
            if "http://example.org/" in arg_str and not "diabetes#" in arg_str:
                var_name = arg_str.split("/")[-1]
                return "?" + var_name

            # Individual Resource
            return clean_uri(arg_str)

        for result in results["results"]["bindings"]:
            rule_uri = result.get("ruleURI", {}).get("value", "")
            
            if rule_uri not in rules_dict:
                rules_dict[rule_uri] = {
                    "rule_uri": rule_uri,
                    "rule_label": result.get("ruleLabel", {}).get("value", "Unlabeled Rule"),
                    "comment": result.get("comment", {}).get("value", ""),
                    "is_enabled": result.get("isEnabled", {}).get("value", "true"),
                    "body_atoms": [],
                    "head_atoms": []
                }
            
            part = result.get("part", {}).get("value", "body")
            atom_type = clean_uri(result.get("atomType", {}).get("value", ""))
            
            pred = clean_uri(result.get("pred", {}).get("value", ""))
            arg1 = format_arg(result.get("arg1", {}).get("value", ""))
            arg2 = format_arg(result.get("arg2", {}).get("value", ""))
            
            builtin = clean_uri(result.get("builtin", {}).get("value", ""))
            b_arg1 = format_arg(result.get("builtinArg1", {}).get("value", ""))
            b_arg2 = format_arg(result.get("builtinArg2", {}).get("value", ""))
            
            atom_str = ""
            
            # 1. Class Atom
            if "ClassAtom" in atom_type and pred and arg1:
                atom_str = f"{pred}({arg1})"
            # 2. Individual / Datavalued Property Atom (ดึงพวก ex:hasSBP, ex:hasTotalCholesterol ฯลฯ)
            elif pred and arg1 and arg2:
                atom_str = f"{pred}({arg1}, {arg2})"
            # 3. Builtin Atom
            elif "BuiltinAtom" in atom_type and builtin and b_arg1:
                if b_arg2:
                    atom_str = f"{builtin}({b_arg1}, {b_arg2})"
                else:
                    atom_str = f"{builtin}({b_arg1})"

            if atom_str:
                target_list = rules_dict[rule_uri]["body_atoms"] if part == "body" else rules_dict[rule_uri]["head_atoms"]
                if atom_str not in target_list:
                    target_list.append(atom_str)

        # ประกอบร่าง String
        rules_list = []
        for r in rules_dict.values():
            body_str = " ^ ".join(r["body_atoms"])
            head_str = " ^ ".join(r["head_atoms"])
            full_rule_str = f"{body_str} -> {head_str}" if head_str else body_str
            
            rules_list.append({
                "rule_uri": r["rule_uri"],
                "rule_label": r["rule_label"],
                "comment": r["comment"],
                "is_enabled": r["is_enabled"],
                "full_rule": full_rule_str
            })

        # เรียงลำดับ S1, S2, S3...
        def natural_sort_key(rule):
            label = rule.get("rule_label", "")
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', label)]

        rules_list.sort(key=natural_sort_key)

        return {"success": True, "count": len(rules_list), "data": rules_list}
        
    except Exception as e:
        print(f"❌ Error fetching SWRL rules: {e}")
        return {"success": False, "message": str(e)}

# =========================================================
# ⚙️ Helper Functions สำหรับสร้าง SPARQL / RDF
# =========================================================

def _execute_sparql_update(sparql_query):
    """Helper function สำหรับส่งคำสั่ง SPARQL UPDATE ไปยัง GraphDB WRITE Endpoint"""
    sparql_write_client = SPARQLWrapper(GRAPHDB_WRITE)
    sparql_write_client.setMethod(POST)
    sparql_write_client.setQuery(sparql_query)
    try:
        sparql_write_client.query()
        return True, "Success"
    except Exception as e:
        print(f"❌ SPARQL Update Error: {e}")
        return False, str(e)


def _parse_swrl_atom_to_triples(atom_str, atom_uri, prefix_ex):
    """แปลงข้อความ Atom ให้เป็น RDF Triples ปลอดภัยจาก Syntax Error และ Pellet Error"""
    atom_str = atom_str.strip()
    triples = []
    
    def resolve_arg(arg):
        arg = arg.strip()
        if arg.startswith('?'):
            var_uri = f"urn:swrl:var#{arg[1:]}"
            triples.append(f"<{var_uri}> a swrl:Variable .")
            return f"<{var_uri}>", "var"
        elif arg.startswith("ex:"):
            return f"<{prefix_ex}{arg[3:]}>", "individual"
        elif arg.startswith("http://") or arg.startswith("https://"):
            return f"<{arg}>", "individual"
        elif arg.startswith('"') and arg.endswith('"'):
            return f'{arg}^^xsd:string', "literal"
        elif arg.replace('.', '', 1).isdigit():
            return f'"{arg}"^^xsd:decimal', "literal"
        else:
            # ข้อความทั่วไปถือเป็น String Literal
            return f'"{arg}"^^xsd:string', "literal"

    # 1. Builtin Atom -> e.g. swrlb:greaterThan(?w, 120)
    builtin_match = re.match(r'^(swrlb:\w+)\((.+)\)$', atom_str)
    if builtin_match:
        builtin_name = builtin_match.group(1).replace("swrlb:", "http://www.w3.org/2003/11/swrlb#")
        args_raw = [a.strip() for a in builtin_match.group(2).split(',')]
        
        args_list_uri = f"{atom_uri}_args_1"
        triples.append(f"<{atom_uri}> a swrl:BuiltinAtom ;")
        triples.append(f"          swrl:builtin <{builtin_name}> ;")
        triples.append(f"          swrl:arguments <{args_list_uri}> .")
        
        for i, arg in enumerate(args_raw):
            curr_list = f"{atom_uri}_args_{i+1}"
            next_list = f"<{atom_uri}_args_{i+2}>" if i + 1 < len(args_raw) else "rdf:nil"
            arg_val, _ = resolve_arg(arg)
            triples.append(f"<{curr_list}> rdf:first {arg_val} ; rdf:rest {next_list} .")
            
        return "\n".join(triples)

    # 2. Class Atom & Property Atom
    atom_match = re.match(r'^([\w:-]+)\((.+)\)$', atom_str)
    if atom_match:
        pred_raw = atom_match.group(1)
        args_raw = [a.strip() for a in atom_match.group(2).split(',')]
        
        if pred_raw.startswith("ex:"):
            pred_uri = f"{prefix_ex}{pred_raw[3:]}"
        elif ":" in pred_raw:
            pred_uri = pred_raw
        else:
            pred_uri = f"{prefix_ex}{pred_raw}"

        # Class Atom (1 argument) -> e.g. ex:Patient(?p)
        if len(args_raw) == 1:
            arg1_val, _ = resolve_arg(args_raw[0])
            triples.append(f"<{atom_uri}> a swrl:ClassAtom ;")
            triples.append(f"          swrl:classPredicate <{pred_uri}> ;")
            triples.append(f"          swrl:argument1 {arg1_val} .")
            
        # Property Atom (2 arguments)
        elif len(args_raw) == 2:
            arg1_val, arg1_type = resolve_arg(args_raw[0])
            arg2_val, arg2_type = resolve_arg(args_raw[1])
            
            # ถ้าตัวแปรที่ 2 เป็น Literal (ข้อความ/ตัวเลข) ต้องใช้ DatavaluedPropertyAtom
            if arg2_type == "literal":
                triples.append(f"<{atom_uri}> a swrl:DatavaluedPropertyAtom ;")
            else:
                triples.append(f"<{atom_uri}> a swrl:IndividualPropertyAtom ;")
                
            triples.append(f"          swrl:propertyPredicate <{pred_uri}> ;")
            triples.append(f"          swrl:argument1 {arg1_val} ;")
            triples.append(f"          swrl:argument2 {arg2_val} .")
            
        return "\n".join(triples)

    return ""


def _build_rule_insert_query(rule_label, comment, swrl_expression, is_enabled="true", target_rule_uri=None):
    """ประกอบร่าง SPARQL INSERT query"""
    prefix_ex = "http://example.org/diabetes#"
    
    clean_label = re.sub(r'\W+', '_', rule_label.strip())
    rule_uri = target_rule_uri or f"{prefix_ex}Rule_{clean_label}"
    
    if "->" in swrl_expression:
        body_part, head_part = swrl_expression.split("->", 1)
    else:
        body_part, head_part = swrl_expression, ""

    body_atoms_str = [a.strip() for a in body_part.split("^") if a.strip()]
    head_atoms_str = [a.strip() for a in head_part.split("^") if a.strip()]

    insert_triples = [
        f"<{rule_uri}> a swrl:Imp ;",
        f'          rdfs:label "{rule_label}" ;',
        f'          rdfs:comment "{comment}" ;',
        f'          swrla:isRuleEnabled "{is_enabled}"^^xsd:boolean .'
    ]

    def build_atom_list(rule_part_name, atoms_list):
        if not atoms_list: 
            return
            
        for i, atom_str in enumerate(atoms_list):
            unique_id = uuid.uuid4().hex
            atom_uri = f"{prefix_ex}atom_{unique_id}"
            list_node = f"{prefix_ex}list_{rule_part_name}_{unique_id}"
            
            if i == 0:
                insert_triples.append(f"<{rule_uri}> swrl:{rule_part_name} <{list_node}> .")

            insert_triples.append(f"<{list_node}> rdf:first <{atom_uri}> .")

            atom_triples = _parse_swrl_atom_to_triples(atom_str, atom_uri, prefix_ex)
            if atom_triples:
                insert_triples.append(atom_triples)

            if i < len(atoms_list) - 1:
                next_list_node = f"<{prefix_ex}list_{rule_part_name}_{uuid.uuid4().hex}>"
            else:
                next_list_node = "rdf:nil"
                
            insert_triples.append(f"<{list_node}> rdf:rest {next_list_node} .")

    build_atom_list("body", body_atoms_str)
    build_atom_list("head", head_atoms_str)

    query = f"""
    PREFIX swrl: <http://www.w3.org/2003/11/swrl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX swrla: <http://swrl.stanford.edu/ontologies/3.3/swrla.owl#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX ex: <{prefix_ex}>

    INSERT DATA {{
        {"  ".join(insert_triples)}
    }}
    """
    return query, rule_uri


# =========================================================
# 🟢 1. ฟังก์ชันเพิ่มกฎ SWRL (Add Rule)
# =========================================================

def add_swrl_rule(rule_label, comment, swrl_expression):
    """สร้างกฎ SWRL ใหม่ลง GraphDB"""
    try:
        sparql_query, _ = _build_rule_insert_query(rule_label, comment, swrl_expression)
        success, err_msg = _execute_sparql_update(sparql_query)

        if success:
            return {"success": True, "message": f"เพิ่มกฎ SWRL '{rule_label}' สำเร็จ"}
        return {"success": False, "message": f"ไม่สามารถบันทึกกฎได้: {err_msg}"}

    except Exception as e:
        print(f"❌ Error adding SWRL rule: {e}")
        return {"success": False, "message": str(e)}


# =========================================================
# 🗑️ 2. ฟังก์ชันลบกฎ SWRL (Delete Rule)
# =========================================================

def delete_swrl_rule(rule_uri):
    """ลบกฎ SWRL และโหนด Blank Nodes ทั้งหมดที่เชื่อมโยงอยู่ ออกจาก GraphDB"""
    try:
        if not rule_uri:
            return {"success": False, "message": "กรุณาระบุ rule_uri ที่ต้องการลบ"}

        sparql_query = f"""
        PREFIX swrl: <http://www.w3.org/2003/11/swrl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        DELETE {{
            <{rule_uri}> ?p ?o .
            ?listNode ?lp ?lo .
            ?atomNode ?ap ?ao .
            ?argsNode ?argsp ?argso .
        }}
        WHERE {{
            <{rule_uri}> ?p ?o .
            OPTIONAL {{
                <{rule_uri}> (swrl:body|swrl:head)/rdf:rest* ?listNode .
                ?listNode ?lp ?lo .
                OPTIONAL {{
                    ?listNode rdf:first ?atomNode .
                    ?atomNode ?ap ?ao .
                    OPTIONAL {{
                        ?atomNode swrl:arguments/rdf:rest* ?argsNode .
                        ?argsNode ?argsp ?argso .
                    }}
                }}
            }}
        }}
        """

        success, err_msg = _execute_sparql_update(sparql_query)
        if success:
            return {"success": True, "message": "ลบกฎออกจาก GraphDB เรียบร้อยแล้ว"}
        return {"success": False, "message": f"ไม่สามารถลบกฎได้: {err_msg}"}

    except Exception as e:
        print(f"❌ Error deleting SWRL rule: {e}")
        return {"success": False, "message": str(e)}


# =========================================================
# ✏️ 3. ฟังก์ชันแก้ไขกฎ SWRL (Update Rule)
# =========================================================

def update_swrl_rule(rule_uri, rule_label, comment, swrl_expression, is_enabled="true"):
    """แก้ไขรายละเอียดกฎ SWRL ที่มีอยู่แล้ว (ลบโครงสร้างเดิม แล้วเขียนโครงสร้างใหม่ทับ)"""
    try:
        # 1. ลบโครงสร้างเดิมของกฎนี้ออกก่อน
        del_res = delete_swrl_rule(rule_uri)
        if not del_res["success"]:
            return del_res

        # 2. เขียนโครงสร้างกฎใหม่เข้าไปแทนที่เดิม
        sparql_query, _ = _build_rule_insert_query(
            rule_label, comment, swrl_expression, is_enabled, target_rule_uri=rule_uri
        )
        success, err_msg = _execute_sparql_update(sparql_query)

        if success:
            return {"success": True, "message": f"แก้ไขกฎ '{rule_label}' เรียบร้อยแล้ว"}
        return {"success": False, "message": f"ไม่สามารถบันทึกการแก้ไขได้: {err_msg}"}

    except Exception as e:
        print(f"❌ Error updating SWRL rule: {e}")
        return {"success": False, "message": str(e)}


# =========================================================
# 🔘 4. ฟังก์ชันเปิด/ปิดการใช้งานกฎ (Toggle Rule Status)
# =========================================================

def toggle_swrl_rule_status(rule_uri, is_enabled):
    """สลับสถานะการเปิดใช้งานกฎ (true / false) ผ่าน swrla:isRuleEnabled"""
    try:
        status_str = "true" if str(is_enabled).lower() in ["true", "1"] else "false"

        sparql_query = f"""
        PREFIX swrla: <http://swrl.stanford.edu/ontologies/3.3/swrla.owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        DELETE {{
            <{rule_uri}> swrla:isRuleEnabled ?oldStatus .
        }}
        INSERT {{
            <{rule_uri}> swrla:isRuleEnabled "{status_str}"^^xsd:boolean .
        }}
        WHERE {{
            OPTIONAL {{ <{rule_uri}> swrla:isRuleEnabled ?oldStatus . }}
        }}
        """

        success, err_msg = _execute_sparql_update(sparql_query)
        if success:
            return {"success": True, "message": f"อัปเดตสถานะกฎเป็น {status_str} สำเร็จ"}
        return {"success": False, "message": f"ไม่สามารถเปลี่ยนสถานะได้: {err_msg}"}

    except Exception as e:
        print(f"❌ Error toggling SWRL status: {e}")
        return {"success": False, "message": str(e)}