import re
import json
from decimal import Decimal, InvalidOperation
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

def preview_swrl_rule(swrl_expression):
    """
    ✅ [NEW] Dry-run: แกะ swrl_expression ออกมาดูว่าแต่ละ argument จะถูกตีความ
    เป็น individual/literal/variable แบบไหน โดย 'ไม่เขียนอะไรลง GraphDB'
    ใช้เช็คก่อนกด save จริงทุกครั้ง เพื่อจับกรณีลืมใส่ 'ex:' หรือลืม quote
    ก่อนที่จะไปเป็นบั๊กเงียบๆ ในกฎจริง
    """
    prefix_ex = "http://example.org/diabetes#"
    if "->" in swrl_expression:
        body_part, head_part = swrl_expression.split("->", 1)
    else:
        body_part, head_part = swrl_expression, ""

    body_atoms_str = [a.strip() for a in body_part.split("^") if a.strip()]
    head_atoms_str = [a.strip() for a in head_part.split("^") if a.strip()]

    def preview_atom(atom_str):
        atom_str = atom_str.strip()
        warnings = []

        def resolve_arg_preview(arg):
            arg = arg.strip()
            if arg.startswith('?'):
                return arg, "variable"
            elif arg.startswith("ex:"):
                return f"{prefix_ex}{arg[3:]}", "individual"
            elif arg.startswith("http://") or arg.startswith("https://"):
                return arg, "individual"
            elif arg.startswith('"') and arg.endswith('"'):
                return arg, "literal (string)"
            elif re.match(r'^-?\d+(\.\d+)?$', arg):
                return arg, "literal (decimal)"
            elif not arg:
                warnings.append(
                    "พบ argument ว่างเปล่า (อาจพิมพ์ comma เกิน หรือเว้นวรรคผิดตำแหน่ง) "
                    "ถ้าบันทึกแบบนี้ Pellet อาจ error ทันที ('subject cannot be null')"
                )
                return "(ว่างเปล่า ❌)", "EMPTY — ห้ามบันทึก"
            else:
                warnings.append(
                    f"'{arg}' ไม่มี 'ex:'/quote นำหน้า -> จะถูกตีความเป็น individual "
                    f"'ex:{arg}' โดยอัตโนมัติ (ถ้าตั้งใจให้เป็นข้อความ ให้ใส่ quote)"
                )
                return f"{prefix_ex}{arg}", "individual (auto-guessed ⚠️)"

        builtin_match = re.match(r'^(swrlb:\w+)\((.+)\)$', atom_str)
        if builtin_match:
            args_raw = [a.strip() for a in builtin_match.group(2).split(',')]
            parsed = [resolve_arg_preview(a) for a in args_raw]
            return {"atom": atom_str, "kind": "builtin", "args": parsed, "warnings": warnings}

        atom_match = re.match(r'^([\w:-]+)\((.+)\)$', atom_str)
        if atom_match:
            pred_raw = atom_match.group(1)
            args_raw = [a.strip() for a in atom_match.group(2).split(',')]
            parsed = [resolve_arg_preview(a) for a in args_raw]
            kind = "class_atom" if len(args_raw) == 1 else "property_atom"
            return {"atom": atom_str, "predicate": pred_raw, "kind": kind, "args": parsed, "warnings": warnings}

        return {"atom": atom_str, "kind": "UNPARSEABLE ❌", "args": [], "warnings": [f"อ่านรูปแบบ '{atom_str}' ไม่ออก เช็ค syntax วงเล็บ/comma ให้ดี"]}

    body_preview = [preview_atom(a) for a in body_atoms_str]
    head_preview = [preview_atom(a) for a in head_atoms_str]
    all_warnings = [w for a in body_preview + head_preview for w in a["warnings"]]

    return {
        "body": body_preview,
        "head": head_preview,
        "has_warnings": len(all_warnings) > 0,
        "warnings": all_warnings
    }


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


def _sparql_node_ref(node):
    """Return a valid SPARQL reference for an IRI or blank node."""
    return node if node.startswith("_:") else f"<{node}>"


def _parse_swrl_atom_to_triples(atom_str, atom_uri, prefix_ex):
    """แปลงข้อความ Atom ให้เป็น RDF Triples ปลอดภัยจาก Syntax Error และ Pellet Error"""
    atom_str = atom_str.strip()
    triples = []

    def node_ref(node):
        return node if node.startswith("_:") else f"<{node}>"

    # ✅ [FIX] เดิม resolve_arg เจอคำที่ไม่มี prefix (ลืมพิมพ์ "ex:" นำหน้า) จะ
    # เดาแบบเงียบๆ ว่าเป็น STRING LITERAL (xsd:string) ทำให้ atom ที่ควรจะเป็น
    # ObjectProperty (เช่น hasComplication(?x, NoGeneralComplication)) กลาย
    # เป็นการเปรียบเทียบกับข้อความ "NoGeneralComplication" แทนที่จะเป็น
    # individual ex:NoGeneralComplication จริงๆ -> Pellet ไม่ error แต่กฎ
    # ไม่ match อะไรเลยตลอดไปแบบเงียบๆ (นี่คือสาเหตุที่กฎเคยพังมาก่อน)
    #
    # ตอนนี้เปลี่ยน default: ถ้าเจอ bareword ที่ไม่มี prefix/quote และไม่ใช่ตัวเลข
    # ให้ถือว่าเป็น individual ภายใต้ ex: แทน (เพราะดูจากกฎทั้งหมดในระบบ ไม่มี
    # ข้อไหนตั้งใจใช้ bareword-ไม่มี-quote เป็น string literal จริงๆเลยสักข้อ
    # string literal ทุกตัวถูก quote ไว้หมด) พร้อม print คำเตือนให้เห็นตอน save
    def resolve_arg(arg):
        arg = arg.strip()
        if arg.startswith('?'):
            var_uri = f"http://example.org/{arg[1:]}"
            triples.append(f"<{var_uri}> a swrl:Variable .")
            return f"<{var_uri}>", "var"
        elif arg.startswith("ex:"):
            return f"<{prefix_ex}{arg[3:]}>", "individual"
        elif arg.startswith("http://") or arg.startswith("https://"):
            return f"<{arg}>", "individual"
        elif arg.startswith('"') and arg.endswith('"'):
            return f'{arg}^^xsd:string', "literal"
        elif re.match(r'^-?\d+(\.\d+)?$', arg):
            return f'"{arg}"^^xsd:decimal', "literal"
        else:
            # ⚠️ [FIX] เช็คก่อนว่า arg ว่างเปล่าไหม (เช่น พิมพ์ comma เกิน/เว้นวรรคผิด
            # ทำให้เหลือ argument ว่างๆ) ถ้าปล่อยผ่านจะได้ IRI พัง <prefix#> (จบที่ # เฉยๆ)
            # ซึ่งเป็นสาเหตุที่ทำให้ Pellet error "subject cannot be null" ได้
            if not arg:
                raise ValueError(
                    "พบ argument ว่างเปล่าในกฎ (อาจพิมพ์ comma เกิน หรือเว้นวรรคผิดตำแหน่ง) "
                    "กรุณาตรวจสอบ syntax ของกฎก่อนบันทึกอีกครั้ง"
                )
            # bareword ไม่มี prefix/quote -> เดาว่าเป็น individual ภายใต้ ex:
            # (ปลอดภัยกว่าเดิมที่เดาเป็น string literal เงียบๆ) แต่ยัง print
            # เตือนไว้เผื่อผู้ใช้ตั้งใจพิมพ์ผิด/สะกดผิดจริงๆ จะได้เห็นใน log ทันที
            print(f"⚠️ [SWRL WARN] อาร์กิวเมนต์ '{arg}' ไม่มี 'ex:' หรือ quote นำหน้า "
                  f"-> ถือว่าเป็น individual 'ex:{arg}' โดยอัตโนมัติ "
                  f"(ถ้าตั้งใจให้เป็นข้อความ ให้ใส่ quote ครอบ เช่น \"{arg}\")")
            return f"<{prefix_ex}{arg}>", "individual"

    # 1. Builtin Atom -> e.g. swrlb:greaterThan(?w, 120)
    builtin_match = re.match(r'^(swrlb:\w+)\((.+)\)$', atom_str)
    if builtin_match:
        builtin_name = builtin_match.group(1).replace("swrlb:", "http://www.w3.org/2003/11/swrlb#")
        args_raw = [a.strip() for a in builtin_match.group(2).split(',')]
        
        args_list_uri = f"{atom_uri}_args_1"
        triples.append(f"{node_ref(atom_uri)} a swrl:BuiltinAtom ;")
        triples.append(f"          swrl:builtin <{builtin_name}> ;")
        triples.append(f"          swrl:arguments {node_ref(args_list_uri)} .")
        
        for i, arg in enumerate(args_raw):
            curr_list = f"{atom_uri}_args_{i+1}"
            next_list = node_ref(f"{atom_uri}_args_{i+2}") if i + 1 < len(args_raw) else "rdf:nil"
            arg_val, _ = resolve_arg(arg)
            triples.append(f"{node_ref(curr_list)} rdf:first {arg_val} ; rdf:rest {next_list} .")
            
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
            triples.append(f"{node_ref(atom_uri)} a swrl:ClassAtom ;")
            triples.append(f"          swrl:classPredicate <{pred_uri}> ;")
            triples.append(f"          swrl:argument1 {arg1_val} .")
            
        # Property Atom (2 arguments)
        elif len(args_raw) == 2:
            arg1_val, arg1_type = resolve_arg(args_raw[0])
            arg2_val, arg2_type = resolve_arg(args_raw[1])
            
            # ถ้าตัวแปรที่ 2 เป็น Literal (ข้อความ/ตัวเลข) ต้องใช้ DatavaluedPropertyAtom
            data_properties = {
                'hasBMI', 'hasSBP', 'hasDBP', 'hasWeight', 'hasHeight',
                'hasFPG', 'hasLDL', 'hasHDL', 'hasTriglyceride',
                'hasTotalCholesterol', 'hasKetone', 'hasMicroalbuminurin', 'metValue',
            }
            if arg2_type == "literal" or pred_uri.removeprefix(prefix_ex) in data_properties:
                triples.append(f"{node_ref(atom_uri)} a swrl:DatavaluedPropertyAtom ;")
            else:
                triples.append(f"{node_ref(atom_uri)} a swrl:IndividualPropertyAtom ;")
                
            triples.append(f"          swrl:propertyPredicate <{pred_uri}> ;")
            triples.append(f"          swrl:argument1 {arg1_val} ;")
            triples.append(f"          swrl:argument2 {arg2_val} .")
            
        return "\n".join(triples)

    return ""


def _build_rule_insert_query(rule_label, comment, swrl_expression, is_enabled="true", target_rule_uri=None):
    """ประกอบร่าง SPARQL INSERT query"""
    prefix_ex = "http://example.org/diabetes#"
    
    clean_label = re.sub(r'\W+', '_', rule_label.strip())
    rule_uri = target_rule_uri or f"_:rule_{uuid.uuid4().hex}"
    
    if "->" in swrl_expression:
        body_part, head_part = swrl_expression.split("->", 1)
    else:
        body_part, head_part = swrl_expression, ""

    body_atoms_str = [a.strip() for a in body_part.split("^") if a.strip()]
    head_atoms_str = [a.strip() for a in head_part.split("^") if a.strip()]

    if not body_atoms_str or not head_atoms_str:
        raise ValueError("กฎ SWRL ต้องมีทั้ง body และ head คั่นด้วย ->")

    insert_triples = [
        f"{_sparql_node_ref(rule_uri)} a swrl:Imp ;",
        f'          rdfs:label {json.dumps(rule_label, ensure_ascii=False)} ;',
        f'          rdfs:comment {json.dumps(comment, ensure_ascii=False)} ;',
        f'          swrla:isRuleEnabled "{is_enabled}"^^xsd:boolean .'
    ]

    def build_atom_list(rule_part_name, atoms_list):
        if not atoms_list: 
            return

        list_nodes = [
            f"_:list_{rule_part_name}_{uuid.uuid4().hex}"
            for _ in atoms_list
        ]

        for i, atom_str in enumerate(atoms_list):
            unique_id = uuid.uuid4().hex
            atom_uri = f"_:atom_{unique_id}"
            list_node = list_nodes[i]
            
            if i == 0:
                insert_triples.append(f"{_sparql_node_ref(rule_uri)} swrl:{rule_part_name} {list_node} .")

            insert_triples.append(f"{list_node} a swrl:AtomList .")
            insert_triples.append(f"{list_node} rdf:first {atom_uri} .")

            atom_triples = _parse_swrl_atom_to_triples(atom_str, atom_uri, prefix_ex)
            if not atom_triples:
                raise ValueError(f"ไม่สามารถอ่าน atom ของกฎได้: {atom_str}")
            if not atom_str.startswith('swrlb:') and "(" in atom_str and "," in atom_str and "swrl:argument2" not in atom_triples:
                raise ValueError(f"property atom ขาด argument2: {atom_str}")
            insert_triples.append(atom_triples)

            if i < len(atoms_list) - 1:
                next_list_node = list_nodes[i + 1]
            else:
                next_list_node = "rdf:nil"
                
            insert_triples.append(f"{list_node} rdf:rest {next_list_node} .")

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

def delete_swrl_rule(rule_uri=None, rule_label=None):
    """ลบกฎ SWRL และโหนด Blank Nodes ทั้งหมดที่เชื่อมโยงอยู่ ออกจาก GraphDB"""
    try:
        if rule_label:
            escaped_label = rule_label.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            rule_ref = "?rule"
            rule_selector = f'?rule rdfs:label "{escaped_label}" .'
        elif rule_uri and not rule_uri.startswith("_:"):
            rule_ref = _sparql_node_ref(rule_uri)
            rule_selector = f"BIND({rule_ref} AS ?rule)"
        else:
            return {"success": False, "message": "กรุณาระบุ rule_uri หรือ rule_label ที่ต้องการลบ"}

        sparql_query = f"""
        PREFIX swrl: <http://www.w3.org/2003/11/swrl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        DELETE {{
            ?rule ?p ?o .
            ?listNode ?lp ?lo .
            ?atomNode ?ap ?ao .
            ?argsNode ?argsp ?argso .
        }}
        WHERE {{
            {rule_selector}
            ?rule ?p ?o .
            OPTIONAL {{
                ?rule (swrl:body|swrl:head)/rdf:rest* ?listNode .
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
        del_res = delete_swrl_rule(rule_uri=rule_uri)
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
        rule_ref = _sparql_node_ref(rule_uri)

        sparql_query = f"""
        PREFIX swrla: <http://swrl.stanford.edu/ontologies/3.3/swrla.owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        DELETE {{
            {rule_ref} swrla:isRuleEnabled ?oldStatus .
        }}
        INSERT {{
            {rule_ref} swrla:isRuleEnabled "{status_str}"^^xsd:boolean .
        }}
        WHERE {{
            OPTIONAL {{ {rule_ref} swrla:isRuleEnabled ?oldStatus . }}
        }}
        """

        success, err_msg = _execute_sparql_update(sparql_query)
        if success:
            return {"success": True, "message": f"อัปเดตสถานะกฎเป็น {status_str} สำเร็จ"}
        return {"success": False, "message": f"ไม่สามารถเปลี่ยนสถานะได้: {err_msg}"}

    except Exception as e:
        print(f"❌ Error toggling SWRL status: {e}")
        return {"success": False, "message": str(e)}


# Form options, validation and SWRL compilation
EX = 'http://example.org/diabetes#'
CATEGORIES = {'patient': 'ข้อมูลผู้ป่วย', 'physical': 'ผลตรวจสุขภาพ',
              'lab': 'ผลตรวจเลือด', 'complication': 'ภาวะแทรกซ้อน'}
NUMBERS = {
    'bmi': ('physical', 'ค่า BMI', 'kg/m²', 'hasBMI'),
    'sbp': ('physical', 'ความดันตัวบน', 'mmHg', 'hasSBP'),
    'dbp': ('physical', 'ความดันตัวล่าง', 'mmHg', 'hasDBP'),
    'weight': ('physical', 'น้ำหนัก', 'kg', 'hasWeight'),
    'height': ('physical', 'ส่วนสูง', 'cm', 'hasHeight'),
    'fpg': ('lab', 'น้ำตาลขณะอดอาหาร', 'mg/dL', 'hasFPG'),
    'ldl': ('lab', 'LDL', 'mg/dL', 'hasLDL'),
    'hdl': ('lab', 'HDL', 'mg/dL', 'hasHDL'),
    'tri': ('lab', 'ไตรกลีเซอไรด์', 'mg/dL', 'hasTriglyceride'),
    'chol': ('lab', 'คอเลสเตอรอลรวม', 'mg/dL', 'hasTotalCholesterol'),
}
OPERATORS = {'gte': 'greaterThanOrEqual', 'gt': 'greaterThan',
             'lte': 'lessThanOrEqual', 'lt': 'lessThan', 'eq': 'equal'}
OP_LABELS = {'gte': 'ตั้งแต่', 'gt': 'มากกว่า', 'lte': 'ไม่เกิน', 'lt': 'น้อยกว่า', 'eq': 'เท่ากับ'}
OUTPUTS = {'warning': 'hasPatientWarning', 'exercise': 'recommendedExercise', 'avoid': 'avoidExercise',
           'intensity': 'intensityOfExercise', 'frequency': 'exerciseFrequency'}
INTENSITY_MET = {
    EX + 'Light': ('MET < 3', [('lessThan', '3')]),
    EX + 'Moderate': ('3 ≤ MET ≤ 6', [('greaterThanOrEqual', '3'), ('lessThanOrEqual', '6')]),
    EX + 'Vigorous': ('MET > 6', [('greaterThan', '6')]),
}
OBJECT_INPUTS = {'type': ('patient', 'ประเภทเบาหวาน', 'diabetType'),
                 'special': ('complication', 'ภาวะแทรกซ้อนในผลตรวจสุขภาพ', 'hasSpecialComplication'),
                 'comorbidity': ('complication', 'โรคร่วม (ผลประเมิน)', 'hasComorbidity'),
                 'complication': ('complication', 'ภาวะแทรกซ้อน (ผลประเมิน)', 'hasComplication')}


def get_builder_catalog():
    client = SPARQLWrapper(GRAPHDB_READ)
    client.setTimeout(30)
    client.setReturnFormat(JSON)
    client.setQuery('''
        PREFIX ex: <http://example.org/diabetes#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX swrl: <http://www.w3.org/2003/11/swrl#>
        SELECT DISTINCT ?kind ?item ?label ?description ?parent WHERE {
          {
            VALUES (?kind ?class) {
                ("type" ex:DiabetType) ("type" ex:DiabeteType) ("type" ex:DiabetesType)
                ("special" ex:Complication) ("complication" ex:Complication)
                ("comorbidity" ex:Comorbidity) ("warning" ex:PatientWarning)
                ("avoid" ex:WarningAvoidExercise) ("intensity" ex:Intensity) ("frequency" ex:Frequency)
            }
            ?item rdf:type/rdfs:subClassOf* ?class .
          } UNION {
            VALUES (?kind ?property) {
                ("type" ex:diabetType) ("special" ex:hasSpecialComplication)
                ("comorbidity" ex:hasComorbidity) ("complication" ex:hasComplication)
                ("warning" ex:hasPatientWarning) ("avoid" ex:avoidExercise)
                ("intensity" ex:intensityOfExercise) ("frequency" ex:exerciseFrequency)
            }
            { ?subject ?property ?item }
            UNION { ?atom swrl:propertyPredicate ?property ; swrl:argument2 ?item }
          } UNION {
            BIND("exercise" AS ?kind)
            { ?item rdfs:subClassOf* ex:Exercise }
            UNION { ?item rdf:type ex:KindOfExercise }
            UNION { ?activity ex:hasKindOfExercise ?item }
            OPTIONAL { ?item rdfs:subClassOf ?parent }
          }
            FILTER(isIRI(?item))
            FILTER NOT EXISTS { ?item rdf:type swrl:Variable }
            OPTIONAL { ?item rdfs:label ?label }
            OPTIONAL { ?item ex:description ?description }
        }
    ''')
    groups = {key: {} for key in (*OBJECT_INPUTS, *OUTPUTS)}
    for row in client.query().convert()['results']['bindings']:
        kind, uri = row['kind']['value'], row['item']['value']
        if kind not in groups or not uri.startswith(EX) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]*', uri[len(EX):]):
            continue
        candidates = [row[k] for k in ('description', 'label') if row.get(k, {}).get('value')]
        best = max(candidates, key=lambda v: (v.get('xml:lang', '').startswith('th'), v.get('xml:lang', '') == ''), default={})
        label = best.get('value', uri[len(EX):])
        rank = (best.get('xml:lang', '').startswith('th'), bool(candidates), label)
        if uri not in groups[kind] or rank > groups[kind][uri][0]:
            groups[kind][uri] = (rank, {'value': uri, 'label': label, 'parent': row.get('parent', {}).get('value', '')})
    groups = {key: sorted((v[1] for v in items.values()), key=lambda v: v['label']) for key, items in groups.items()}
    for item in groups['intensity']:
        item['met_label'] = INTENSITY_MET.get(item['value'], ('ยังไม่ได้กำหนดช่วง MET', []))[0]
    fields = {key: {'category': category, 'label': label, 'unit': unit}
              for key, (category, label, unit, _) in NUMBERS.items()}
    for key, (category, label, _) in OBJECT_INPUTS.items():
        fields[key] = {'category': category, 'label': label, 'options': groups[key], 'multiple': key != 'type'}
    # A negative named finding is selectable only when it exists in the graph;
    # it is still matched as a positive assertion, never inferred from missing data.
    for key, label in [('ketone', 'ผลตรวจคีโตน'), ('micro', 'ผลไมโครอัลบูมินในปัสสาวะ')]:
        fields[key] = {'category': 'lab', 'label': label, 'options': [
            {'value': 'Negative', 'label': 'Negative'}, {'value': 'Positive', 'label': 'Positive'}]}
    return {'categories': CATEGORIES, 'fields': fields, 'results': {key: groups[key] for key in OUTPUTS}}


def compile_builder_rule(data, catalog):
    if not isinstance(data, dict):
        raise ValueError('รูปแบบข้อมูลไม่ถูกต้อง')
    name = data.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 250:
        raise ValueError('กรุณาระบุชื่อกฎไม่เกิน 250 ตัวอักษร')
    conditions = data.get('conditions')
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 30:
        raise ValueError('กรุณาเลือกเงื่อนไข 1–30 ข้อ')
    outcomes = data.get('outputs', [{'action': data.get('action'), 'result': data.get('result')}])
    if not isinstance(outcomes, list) or not 1 <= len(outcomes) <= 30:
        raise ValueError('กรุณาเลือกผลลัพธ์ 1–30 รายการ')

    def selected(options, value):
        item = next((item for item in options if item['value'] == value), None)
        if not item:
            raise ValueError('รายการที่เลือกไม่มีในระบบแล้ว กรุณาโหลดหน้าใหม่และเลือกอีกครั้ง')
        uri = item['value']
        if not uri.startswith(EX) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]*', uri[len(EX):]):
            raise ValueError('รหัสรายการไม่ถูกต้อง')
        return 'ex:' + uri[len(EX):], item['label']

    body, summary = ['ex:Patient(?p)'], []

    def numeric(value):
        if not isinstance(value, (str, int, float)) or isinstance(value, bool) or len(str(value)) > 30:
            raise ValueError('กรุณาระบุตัวเลขที่ถูกต้อง')
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ValueError('กรุณาระบุตัวเลขที่ถูกต้อง') from None
        if not number.is_finite() or number < 0 or number > 1000000 or number.as_tuple().exponent < -10:
            raise ValueError('ตัวเลขต้องอยู่ระหว่าง 0 ถึง 1,000,000 และทศนิยมไม่เกิน 10 ตำแหน่ง')
        return number

    def link(atom):
        if atom not in body:
            body.append(atom)

    for i, condition in enumerate(conditions):
        if not isinstance(condition, dict):
            raise ValueError('เงื่อนไขไม่ถูกต้อง')
        field, op, value = (condition.get(key) for key in ('field', 'op', 'value'))
        if not isinstance(field, str) or field not in catalog['fields']:
            raise ValueError('ไม่รู้จักข้อมูลที่เลือกเป็นเงื่อนไข')
        if field in OBJECT_INPUTS:
            if op != 'eq':
                raise ValueError('ข้อมูลประเภทนี้รองรับเฉพาะรายการที่บันทึกว่ามี ไม่รองรับการเดาว่าไม่มี')
            term, label = selected(catalog['fields'][field]['options'], value)
            if field == 'type':
                body.append(f'ex:diabetType(?p, {term})')
                summary.append(f'เป็น {label}')
            elif field == 'special':
                link('ex:hasPhysicalExam(?p, ?pe)')
                body.append(f'ex:hasSpecialComplication(?pe, {term})')
                summary.append(f'มี {label}')
            else:
                body.append(f'ex:{OBJECT_INPUTS[field][2]}(?p, {term})')
                summary.append(f'{OBJECT_INPUTS[field][1]}: {label}')
        elif field in ('ketone', 'micro'):
            if op != 'eq' or value not in ('Negative', 'Positive'):
                raise ValueError('ผลตรวจต้องเป็น Negative หรือ Positive')
            link('ex:hasLabExam(?p, ?le)')
            prop = 'hasKetone' if field == 'ketone' else 'hasMicroalbuminurin'
            body.append(f'ex:{prop}(?le, "{value}")')
            summary.append(f'{catalog["fields"][field]["label"]}: {value}')
        else:
            if not isinstance(op, str) or op not in OPERATORS:
                raise ValueError('เงื่อนไขเปรียบเทียบไม่ถูกต้อง')
            number = numeric(value)
            category, label, unit, prop = NUMBERS[field]
            subject = '?pe' if category == 'physical' else '?le'
            link(f'ex:{"hasPhysicalExam" if category == "physical" else "hasLabExam"}(?p, {subject})')
            body.append(f'ex:{prop}({subject}, ?v{i})')
            body.append(f'swrlb:{OPERATORS[op]}(?v{i}, {format(number, "f")})')
            summary.append(f'{label} {OP_LABELS[op]} {number} {unit}' + (' ขึ้นไป' if op == 'gte' else ''))
    head, descriptions = [], []
    for index, outcome in enumerate(outcomes):
        if not isinstance(outcome, dict) or not isinstance(outcome.get('action'), str) or outcome['action'] not in OUTPUTS or outcome['action'] == 'intensity':
            raise ValueError('กรุณาเลือกประเภทผลลัพธ์')
        action = outcome['action']
        target, label = selected(catalog['results'].get(action, []), outcome.get('result'))
        if action == 'exercise':
            intensity, intensity_label = selected(catalog['results'].get('intensity', []), outcome.get('intensity'))
            if outcome['intensity'] not in INTENSITY_MET:
                raise ValueError('ความหนักที่เลือกยังไม่ได้กำหนดช่วง MET กรุณาเลือก Light, Moderate หรือ Vigorous')
            met_label, met_conditions = INTENSITY_MET[outcome['intensity']]
            favorites = outcome.get('use_favorites', True)
            if not isinstance(favorites, bool):
                raise ValueError('การเลือกกิจกรรมที่ชอบไม่ถูกต้อง')
            exercise, met, favorite = f'?e{index}', f'?met{index}', f'?fe{index}'
            link(f'ex:Exercise({exercise})')
            if target != 'ex:Exercise':
                link(f'{target}({exercise})')
            if favorites:
                link(f'ex:favoriteExercise(?p, {favorite})')
                link(f'ex:KindOfExercise({favorite})')
                link(f'ex:hasKindOfExercise({exercise}, {favorite})')
            link(f'ex:metValue({exercise}, {met})')
            for comparison, threshold in met_conditions:
                link(f'swrlb:{comparison}({met}, {threshold})')
            head.extend([f'ex:recommendedExercise(?p, {exercise})', f'ex:intensityOfExercise(?p, {intensity})'])
            descriptions.append(f'แนะนำหมวด {label} {met_label} ความหนัก {intensity_label}' + (' เฉพาะหมวดที่ผู้ป่วยชอบ' if favorites else ''))
        else:
            head.append(f'ex:{OUTPUTS[action]}(?p, {target})')
            descriptions.append(f'{action}: {label}')
    expression = ' ^ '.join(body) + ' -> ' + ' ^ '.join(dict.fromkeys(head))
    comment = 'ถ้าผู้ป่วย' + ' และ'.join(summary) + ' ให้' + ' และ'.join(descriptions)
    return {'rule_label': name.strip(), 'comment': comment, 'swrl_expression': expression}
