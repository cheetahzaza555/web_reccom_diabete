import re
from SPARQLWrapper import SPARQLWrapper, JSON
from modules.config import GRAPHDB_READ, GRAPHDB_WRITE

import re
from SPARQLWrapper import SPARQLWrapper, JSON
from modules.config import GRAPHDB_READ, GRAPHDB_WRITE

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