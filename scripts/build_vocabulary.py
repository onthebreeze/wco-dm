#!/usr/bin/env python3
"""Stage B: the intermediate to a linked data vocabulary.

One TTL module per WCO superclass, plus a code-list module. Classes keep their WCO names. Properties
take the dictionary entry name without its object class, so a concept used by several classes is one
IRI with several schema:domainIncludes, which is how vocab.unece.org models the same ground.

Attributes that share a local name and a core data type are one property with many domains. The
WCO definitions are class-specific glosses of the same concept - identificationIdentifier carries
172 of them - so each is kept as a skos:scopeNote naming its class, and nothing is lost. Where the
name matches but the data type does not, the attributes are different things and the later one is
qualified with its class, which is reported in mappings/name-collisions.csv.

    python3 scripts/build_vocabulary.py
"""
import collections
import csv
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _names import camel, class_name, label_from_den, local_name, split_den

ROOT = pathlib.Path(__file__).resolve().parent.parent
INT = ROOT / "intermediate"
ONT = ROOT / "ontology"
MAP = ROOT / "mappings"

# The vocabulary always carries the WCO-owned namespace. Only the site build rewrites it for
# whatever host is serving, so ontology/ is the same file whoever builds it and whatever host it is
# destined for. Putting WCO_BASE here instead would make the committed source depend on an
# environment variable, and a test build would rewrite every published identifier.
BASE = "https://vocabulary.wcoomd.org/"
MODULES = ["core", "document", "government", "location", "party", "transport"]

# WCO core data types to a range. Code and Identifier carry a code list or scheme rather than a
# literal type, so they are resolved per attribute below.
XSD_OF = {
    "Text": "xsd:string", "Date": "xsd:date", "Date Time": "xsd:dateTime", "DateTime": "xsd:dateTime",
    "Time": "xsd:time", "Numeric": "xsd:decimal", "Percent": "xsd:decimal", "Indicator": "xsd:boolean",
    "Binary Object": "xsd:base64Binary", "Graphic": "xsd:base64Binary", "Picture": "xsd:base64Binary",
    "Sound": "xsd:base64Binary", "Video": "xsd:base64Binary",
}
VALUE_OBJECT_OF = {"Amount": "Amount", "Measure": "Measure", "Quantity": "Quantity"}


def esc(text):
    """A Turtle string literal body."""
    return (text or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ").strip()


def load(name):
    return json.loads((INT / f"{name}.json").read_text())


def code_list_slug(name):
    """AEOProgramTypeCode -> aeo-program-type-code-list. Hyphens go in at the camel-case boundaries
    before lowercasing, so the slug stays readable in a URL.

    The register names a list after the attribute it serves, so "TypeCode" is both a property and a
    list and a reader cannot tell which a link leads to. The suffix settles it: the property is
    "Type code", the list is "TypeCodeList"."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", name or "")
    slug = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return slug if slug.endswith("-list") else slug + "-list"


def code_list_label(name):
    n = (name or "").strip()
    return n if n.lower().endswith("list") else n + "List"


def norm_basis(text):
    return " ".join((text or "").split()).strip().lower()


def is_list_like(ref):
    """A code list reference names a list; some cells carry guidance instead. "ISO 3166-1" names a
    list. "Sea: ITU Standard or Lloyd's number Air: IATA aircraft ID..." is advice to an
    implementer, and minting a code list for it would invent a thing that does not exist."""
    r = " ".join((ref or "").split())
    return bool(r) and len(r) <= 60 and "\n" not in r and "." not in r.rstrip(".")


def external_slug(ref):
    return "external/" + code_list_slug(" ".join((ref or "").split()))


def resolve_range(attr, code_list_slugs, by_basis=None):
    """The range of a property: a code list, a value object, or an xsd type.

    The library names a code list by the basis it draws on rather than by the register's name for
    it, so the join is on that basis string. Twenty-six register entries share the basis "User code
    list" and could not be told apart, so a reference is only turned into a link when exactly one
    register entry carries that basis. The rest keep the reference as text."""
    cdt = (attr.get("core_data_type") or "").strip()
    ref = attr.get("code_list")
    if cdt in ("Code", "Identifier") and ref:
        hit = (by_basis or {}).get(norm_basis(ref))
        if hit and len(hit) == 1:
            return f"wco-cl:{hit[0]}"
        # The register either does not hold this list, or holds several drawing on the same basis
        # and cannot say which. The reference still names a real list, so it becomes one in its own
        # right rather than collapsing to a plain string.
        if is_list_like(ref):
            return f"<{BASE}code-list/{external_slug(ref)}>"
    if cdt in VALUE_OBJECT_OF:
        return f"wco:{VALUE_OBJECT_OF[cdt]}"
    if cdt in ("Code", "Identifier"):
        return "xsd:string"
    return XSD_OF.get(cdt, "xsd:string")


def header(module, label, description):
    return f"""# WCO Data Model vocabulary — {module}.ttl
# Generated by scripts/build_vocabulary.py from intermediate/. Do not edit by hand.
# Source: WCO Data Model version 4.3.0, raw-data/.

@prefix wco:     <{BASE}> .
@prefix wco-mod: <{BASE}module/> .
@prefix wco-cl:  <{BASE}code-list/> .
@prefix ts:      <{BASE}term-status/> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix schema:  <https://schema.org/> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .

wco-mod:{module} a owl:Ontology ;
    rdfs:label "{esc(label)}"@en ;
    dcterms:description "{esc(description)}"@en ;
    dcterms:source "WCO Data Model 4.3.0"@en .

"""


def main():
    classes = load("classes")
    attributes = load("attributes")
    code_lists = load("code-lists")
    data_types = load("data-types")

    ONT.mkdir(exist_ok=True)
    MAP.mkdir(exist_ok=True)
    cl_slugs = {code_list_slug(c["name"]) for c in code_lists}
    by_basis = collections.defaultdict(list)
    for c in code_lists:
        if c.get("basis"):
            by_basis[norm_basis(c["basis"])].append(code_list_slug(c["name"]))

    # --- properties: one IRI per concept, domains gathered from every class that uses it ---
    props, collisions = {}, []
    for a in attributes:
        name = local_name(a["dictionary_entry_name"], a.get("json_tag"))
        if not name:
            continue
        definition = a.get("definition") or ""
        cdt = (a.get("core_data_type") or "").strip()
        key = name
        if name in props and props[name]["core_data_type"] != cdt:
            # Same name, different core data type: different things, so qualify and report.
            key = camel(f"{a['class_name']} {name}")
            collisions.append({
                "local_name": name, "qualified_as": key, "class": a["class_name"],
                "dictionary_entry_name": a["dictionary_entry_name"],
                "existing_core_data_type": props[name]["core_data_type"],
                "this_core_data_type": cdt,
                "this_definition": definition[:160],
                "source_row": a["source"]["row"],
            })
        p = props.setdefault(key, {
            "local": key, "label": label_from_den(a["dictionary_entry_name"], a.get("attr_name")),
            "definition": "",
            "core_data_type": cdt, "glosses": [],
            "domains": [], "ranges": set(), "module": a["module"], "attr_ids": [],
            "code_list_refs": set(),
            "xml_tags": set(), "json_tags": set(), "dens": [], "sources": [],
        })
        if definition:
            p["glosses"].append((class_name(a["class_name"]), definition))
        p["domains"].append(class_name(a["class_name"]))
        p["ranges"].add(resolve_range(a, cl_slugs, by_basis))
        if a.get("code_list"):
            p["code_list_refs"].add(" ".join(a["code_list"].split()))
        p["attr_ids"].append(a["attr_id"])
        if a.get("xml_tag"):
            p["xml_tags"].add(a["xml_tag"])
        if a.get("json_tag"):
            p["json_tags"].add(a["json_tag"])
        p["dens"].append(a["dictionary_entry_name"])
        p["sources"].append(f"{a['source']['sheet']}:{a['source']['row']}")

    # The property's own definition is the gloss that the most classes agree on; the others are
    # kept as scope notes so the class-specific wording survives.
    for p in props.values():
        if not p["glosses"]:
            continue
        counts = collections.Counter(text for _, text in p["glosses"])
        p["definition"] = counts.most_common(1)[0][0]
        p["scope_notes"] = [(cls, text) for cls, text in p["glosses"] if text != p["definition"]]

    # A property belongs to the module of the class that uses it; where several modules use it, it
    # is cross-cutting and belongs in core.
    by_class_module = {class_name(c["class_name"]): c["module"] for c in classes}
    for p in props.values():
        mods = {by_class_module.get(d, "core") for d in p["domains"]}
        p["module"] = mods.pop() if len(mods) == 1 else "core"

    # --- write one file per module ---
    written = collections.Counter()
    for module in MODULES:
        lines = [header(module, f"WCO Data Model — {module}", f"The {module} module of the WCO Data Model 4.3.0 vocabulary.")]
        lines.append("# " + "-" * 74 + "\n# Classes\n# " + "-" * 74 + "\n")
        for c in sorted(classes, key=lambda c: c["class_name"]):
            if c["module"] != module:
                continue
            cn = class_name(c["class_name"])
            lines.append(f"wco:{cn} a owl:Class ;\n    rdfs:label \"{esc(c['class_name'])}\"@en ;")
            if c.get("definition"):
                lines.append(f"    skos:definition \"{esc(c['definition'])}\"@en ;")
            lines.append(f"    wco:classId \"{esc(c['class_id'])}\" ;")
            lines.append(f"    dcterms:source \"{esc(c['source']['file'])} {c['source']['sheet']}:{c['source']['row']}\" ;")
            lines.append(f"    rdfs:isDefinedBy wco-mod:{module} ;\n    wco:termStatus ts:active .\n")
            written[f"class:{module}"] += 1

        lines.append("# " + "-" * 74 + "\n# Properties\n# " + "-" * 74 + "\n")
        for p in sorted((p for p in props.values() if p["module"] == module), key=lambda p: p["local"]):
            kind = "owl:ObjectProperty" if any(r.startswith(("wco:", "wco-cl:")) for r in p["ranges"]) else "owl:DatatypeProperty"
            lines.append(f"wco:{p['local']} a {kind} ;\n    rdfs:label \"{esc(p['label'])}\"@en ;")
            if p["definition"]:
                lines.append(f"    skos:definition \"{esc(p['definition'])}\"@en ;")
            for cls, text in sorted(p.get("scope_notes", [])):
                lines.append(f"    skos:scopeNote \"{esc(cls)}: {esc(text)}\"@en ;")
            domains = sorted(set(p["domains"]))
            lines.append("    schema:domainIncludes " + ", ".join(f"wco:{d}" for d in domains) + " ;")
            lines.append("    schema:rangeIncludes " + ", ".join(sorted(p["ranges"])) + " ;")
            for ref in sorted(p["code_list_refs"]):
                lines.append(f'    wco:codeListBasis "{esc(ref)}"@en ;')
            if p["xml_tags"]:
                lines.append("    wco:xmlTag " + ", ".join(f'"{esc(t)}"' for t in sorted(p["xml_tags"])) + " ;")
            if p["json_tags"]:
                lines.append("    wco:jsonTag " + ", ".join(f'"{esc(t)}"' for t in sorted(p["json_tags"])) + " ;")
            lines.append("    wco:attributeId " + ", ".join(f'"{esc(i)}"' for i in sorted(set(p["attr_ids"]))) + " ;")
            lines.append(f"    dcterms:source \"DataSet 1.2, 1.3, 1.4 rows {', '.join(sorted(set(s.split(':')[-1] for s in p['sources'])))}\" ;")
            lines.append(f"    rdfs:isDefinedBy wco-mod:{module} ;\n    wco:termStatus ts:active .\n")
            written[f"property:{module}"] += 1

        (ONT / f"{module}.ttl").write_text("\n".join(lines))

    # --- core data types as value objects, from Data Set 1.5 ---
    # Amount, Measure and Quantity are ranged at by properties above, so they have to exist as
    # classes; the rest are generated with them because they are the same kind of thing, a value
    # with supplementary components.
    dts = collections.OrderedDict()
    for r in data_types:
        dts.setdefault(r["name"], []).append(r)
    dt_lines = [header("data-types", "WCO Data Model — core data types",
                       "The core data types of the WCO Data Model 4.3.0 and their supplementary components.")]
    for type_name, rows in dts.items():
        cn = class_name(type_name.split(".")[0])
        dt_lines.append(f'wco:{cn} a owl:Class ;\n    rdfs:label "{esc(type_name.split(".")[0].strip())}"@en ;')
        dt_lines.append(f'    skos:definition "The WCO core data type {esc(type_name)}: a value together with its supplementary components."@en ;')
        dt_lines.append(f'    dcterms:source "DataSet 1.5:{rows[0]["source"]["row"]}" ;')
        dt_lines.append(f'    rdfs:isDefinedBy wco-mod:data-types ;\n    wco:termStatus ts:active .\n')
        written["data-type"] += 1
        for r in rows:
            if not r.get("attribute"):
                continue
            comp = local_name(r["attribute"])
            if not comp:
                continue
            rng = f"wco-cl:{code_list_slug(r['code_list'])}" if r.get("code_list") and code_list_slug(r["code_list"]) in cl_slugs else "xsd:string"
            kind = "owl:ObjectProperty" if rng.startswith("wco-cl:") else "owl:DatatypeProperty"
            dt_lines.append(f'wco:{comp} a {kind} ;\n    rdfs:label "{esc(r["attribute"])}"@en ;')
            dt_lines.append(f'    skos:definition "Supplementary component {esc(r["attribute"])} of the {esc(type_name)} core data type."@en ;')
            if r.get("remarks"):
                dt_lines.append(f'    skos:scopeNote "{esc(r["remarks"])}"@en ;')
            dt_lines.append(f'    schema:domainIncludes wco:{cn} ;\n    schema:rangeIncludes {rng} ;')
            dt_lines.append(f'    dcterms:source "DataSet 1.5:{r["source"]["row"]}" ;')
            dt_lines.append(f'    rdfs:isDefinedBy wco-mod:data-types ;\n    wco:termStatus ts:active .\n')
            written["data-type-component"] += 1
    (ONT / "data-types.ttl").write_text("\n".join(dt_lines))

    # --- the machinery module: annotation properties and the two schemes ---
    mach = [header("governance", "WCO Data Model — governance", "Annotation properties and the lifecycle scheme used by the vocabulary itself.")]
    for name, label, comment in [
        ("termStatus", "term status", "Governance lifecycle state of a term; a value from the term-status scheme."),
        ("classId", "class ID", "The class identifier carried by the WCO Data Model library."),
        ("attributeId", "attribute ID", "The attribute identifier carried by the WCO Data Model library."),
        ("xmlTag", "XML tag name", "The XML tag name the WCO Data Model assigns to this property."),
        ("jsonTag", "JSON tag name", "The JSON tag name the WCO Data Model assigns to this property."),
        ("codeListBasis", "code list basis", "The external list a code list is based on, where WCO does not own the values."),
        ("codeListOrigin", "code list origin", "Whether the list is registered in the WCO code list register, or only referenced by the model."),
    ]:
        mach.append(f'wco:{name} a owl:AnnotationProperty ;\n    rdfs:label "{label}"@en ;\n    rdfs:comment "{comment}"@en ;\n    rdfs:isDefinedBy wco-mod:governance .\n')
    mach.append("# The term-status scheme, on the vocab.unece.org lifecycle.\n")
    mach.append('ts:scheme a skos:ConceptScheme ; rdfs:label "WCO vocabulary term status"@en .\n')
    for state, note in [("proposed", "Put forward, not yet part of the published model."),
                        ("active", "Part of the published WCO Data Model."),
                        ("deprecated", "Still published, but its use is discouraged."),
                        ("retired", "Withdrawn; retained so that existing references resolve.")]:
        mach.append(f'ts:{state} a skos:Concept ; skos:inScheme ts:scheme ;\n    skos:prefLabel "{state}"@en ; skos:definition "{note}"@en .\n')
    (ONT / "governance.ttl").write_text("\n".join(mach))

    # --- code lists ---
    cl = [header("code-lists", "WCO Data Model — code lists", "The code lists the WCO Data Model 4.3.0 registers. Twelve carry their values; the rest name an external list.")]
    for c in code_lists:
        slug = code_list_slug(c["name"])
        cl.append(f'wco-cl:{slug} a skos:ConceptScheme ;\n    rdfs:label "{esc(code_list_label(c["name"]))}"@en ;')
        cl.append(f'    skos:altLabel "{esc(c["name"])}"@en ;')
        if c.get("basis"):
            cl.append(f'    wco:codeListBasis "{esc(c["basis"])}"@en ;')
        cl.append(f'    wco:codeListOrigin "registered" ;')
        cl.append(f'    dcterms:source "DataSet 1.6:{c["source"]["row"]}" ;')
        cl.append(f'    rdfs:isDefinedBy wco-mod:code-lists ;\n    wco:termStatus ts:active .\n')
        for code in c["codes"]:
            ident = re.sub(r"[^A-Za-z0-9_.-]", "-", code["code"])
            cl.append(f'<{BASE}code-list/{slug}/{ident}> a skos:Concept ; skos:inScheme wco-cl:{slug} ;\n    skos:notation "{esc(code["code"])}" ;')
            if code.get("description"):
                cl.append(f'    skos:prefLabel "{esc(code["description"])}"@en ;')
            cl.append(f'    wco:termStatus ts:active .\n')
            written["code"] += 1
        written["code-list"] += 1
    # Lists the model references but the register does not hold, or holds ambiguously. They carry
    # no values - the values belong to the external authority - but they give every coded property
    # a code list to resolve to instead of a bare string.
    minted = {}
    for a in attributes:
        ref = a.get("code_list")
        cdt = (a.get("core_data_type") or "").strip()
        if cdt not in ("Code", "Identifier") or not ref or not is_list_like(ref):
            continue
        hit = by_basis.get(norm_basis(ref))
        if hit and len(hit) == 1:
            continue
        minted.setdefault(external_slug(ref), {"ref": " ".join(ref.split()), "shared_with": hit or []})
    if minted:
        cl.append("# " + "-" * 74)
        cl.append("# Referenced lists the register does not hold, or holds under several names.")
        cl.append("# " + "-" * 74 + "\n")
    for slug, info in sorted(minted.items()):
        cl.append(f'<{BASE}code-list/{slug}> a skos:ConceptScheme ;\n    rdfs:label "{esc(info["ref"])}"@en ;')
        cl.append(f'    skos:definition "The code list the WCO Data Model names as {esc(info["ref"])}. '
                  f'Its values are maintained by that authority and are not carried here."@en ;')
        cl.append(f'    wco:codeListBasis "{esc(info["ref"])}"@en ;')
        cl.append('    wco:codeListOrigin "referenced" ;')
        for other in sorted(info["shared_with"]):
            cl.append(f'    skos:related wco-cl:{other} ;')
        cl.append(f'    rdfs:isDefinedBy wco-mod:code-lists ;\n    wco:termStatus ts:active .\n')
        written["referenced-code-list"] += 1
    (ONT / "code-lists.ttl").write_text("\n".join(cl))

    # --- the collision ledger ---
    if collisions:
        with (MAP / "name-collisions.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(collisions[0].keys()))
            w.writeheader()
            w.writerows(collisions)

    print(f"base: {BASE}")
    for k in sorted(written):
        print(f"  {k}: {written[k]}")
    print(f"  properties total: {len(props)} (from {len(attributes)} attributes)")
    print(f"  name collisions qualified: {len(collisions)} -> mappings/name-collisions.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
