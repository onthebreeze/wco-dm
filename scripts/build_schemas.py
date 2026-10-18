#!/usr/bin/env python3
"""Stage D, second half: JSON Schema and JSON-LD context per Information Package.

The library gives meaning, the packages give structure. A package file is a tree of information
paths, each node saying how many times it may occur, so a schema follows directly: a class becomes
an object, an element becomes a typed property, max unbounded becomes an array, and min one becomes
required.

Each derived package - eTIR, Certificate of Origin, Maritime API and the rest - is the same tree cut
down to the nodes it marks, with the ancestors those nodes need, so its schema is generated from the
same source rather than maintained separately.

One schema and one context per message per release. The file name carries the release, so the
4.3.0 artefacts keep the addresses they were published at and the older releases take their own.

    python3 scripts/build_schemas.py            # every release
    WCO_RELEASE=v4.1.0 python3 scripts/build_schemas.py
"""
import json
import os
import pathlib
import re
import sys

import rdflib
from rdflib.namespace import OWL, RDF, RDFS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _overrides  # noqa: E402
import _release  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONT, OUT = ROOT / "ontology", ROOT / "schemas"
# The schemas are a committed artefact and always carry the canonical namespace. Only the site
# build rewrites it for whatever host is serving, exactly as the ontology does: honouring WCO_BASE
# here would bake a test hostname into every $id and every x-wco-term the moment someone built the
# site for a local preview.
SOURCE_BASE = BASE = "https://vocabulary.wcoomd.org/"



def clean_tag(tag, path=None):
    """A tag cell that holds more than one line.

    Two cases. A root tag arrives with the structure name folded in ("cis\\ndeclaration"), where the
    last line is the tag. And ten cells in the 4.3.0 workbooks hold two candidate tags, the same
    pair repeated on rows that need different ones: Invoice/type and Invoice/Issuer/name both say
    "TypeCode\\nName". WCO's own XML schemas take TypeCode on one and Name on the other, which is
    how we know the published schemas are not generated from these spreadsheets. Where the path is
    known, the line that matches the path's last segment is the one meant.
    """
    lines = [t.strip() for t in (tag or "").split("\n") if t.strip()]
    if len(lines) < 2:
        return lines[0] if lines else ""
    if path:
        tail = path.rsplit("/", 1)[-1].lower()
        matching = [t for t in lines if tail and tail in t.lower()]
        if len(matching) == 1:
            return matching[0]
    return lines[-1]


def json_type(fmt):
    """A WCO format to a JSON Schema type. an..35 is a string of up to 35, n..2 an integer of up to
    two digits, a2 exactly two letters."""
    if not fmt:
        return {"type": "string"}
    f = fmt.strip()
    m = re.match(r"^(a|an|n)(\.\.)?(\d+)$", f)
    if not m:
        return {"type": "string", "description": f"WCO format {f}"}
    kind, variable, size = m.group(1), bool(m.group(2)), int(m.group(3))
    if kind == "n":
        # Numeric formats cover identifiers and counts alike; a string with a pattern keeps leading
        # zeros, which a number would lose, and WCO numerics are frequently coded values.
        return {"type": "string", "pattern": rf"^\d{{1,{size}}}$" if variable else rf"^\d{{{size}}}$"}
    out = {"type": "string"}
    if variable:
        out["maxLength"] = size
    else:
        out["minLength"] = out["maxLength"] = size
    return out


def property_iris():
    """WCO attribute ID -> vocabulary IRI, so a context can point at the published term."""
    g = rdflib.Graph()
    for f in sorted(ONT.glob("*.ttl")):
        g.parse(f, format="turtle")
    wco = rdflib.Namespace(SOURCE_BASE)
    out = {}
    for kind in (OWL.DatatypeProperty, OWL.ObjectProperty):
        for s in g.subjects(RDF.type, kind):
            for attr_id in g.objects(s, wco.attributeId):
                out.setdefault(str(attr_id), str(s))
    classes = {}
    for s in g.subjects(RDF.type, OWL.Class):
        for class_id in g.objects(s, wco.classId):
            classes.setdefault(str(class_id), str(s))
    return out, classes


def build_tree(nodes, keep=None):
    """Nodes to a nested dict keyed by path. `keep` limits it to a derived package: a node is kept
    if it is marked, or if a kept node sits below it."""
    by_path = {n["path"]: n for n in nodes}
    if keep is not None:
        wanted = set()
        for n in nodes:
            if keep in (n["used_by"] or []):
                parts = n["path"].split("/")
                for i in range(1, len(parts) + 1):
                    wanted.add("/".join(parts[:i]))
        by_path = {p: n for p, n in by_path.items() if p in wanted}
    children = {}
    for path in by_path:
        parent = path.rsplit("/", 1)[0] if "/" in path else None
        children.setdefault(parent, []).append(path)
    for v in children.values():
        v.sort(key=lambda p: int(by_path[p].get("seq") or 0))
    return by_path, children


def node_schema(path, by_path, children, attr_iris, defs):
    node = by_path[path]
    kids = children.get(path, [])
    if node["type"] == "E" and not kids:
        schema = json_type(node["format"])
        if node.get("definition"):
            schema["description"] = node["definition"]
        if node.get("code_list"):
            schema["x-wco-code-list"] = node["code_list"]
        if node.get("wco_id"):
            schema["x-wco-id"] = node["wco_id"]
            iri = attr_iris.get(node["wco_id"])
            if iri:
                schema["x-wco-term"] = iri.replace(SOURCE_BASE, BASE)
        return schema

    properties, required = {}, []
    for child in kids:
        c = by_path[child]
        tag = clean_tag(c["json_tag"], c["path"]) or c["path"].rsplit("/", 1)[-1]
        sub = node_schema(child, by_path, children, attr_iris, defs)
        if (c.get("max") or "").lower() == "unbounded":
            sub = {"type": "array", "items": sub}
            if (c.get("min") or "0") not in ("0", None):
                sub["minItems"] = int(c["min"])
        properties[tag] = sub
        if (c.get("min") or "0") not in ("0", "", None):
            required.append(tag)

    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if node.get("definition"):
        schema["description"] = node["definition"]
    if node.get("wco_id"):
        schema["x-wco-id"] = node["wco_id"]
    if required:
        schema["required"] = sorted(required)
    return schema


def context_for(by_path, attr_iris, class_iris):
    """A JSON-LD context mapping each tag to its published term. A tag that means different things
    in different places is left out rather than bound to one of them."""
    seen, conflicts = {}, set()
    for node in by_path.values():
        tag = clean_tag(node["json_tag"], node["path"])
        if not tag or not node.get("wco_id"):
            continue
        iri = (attr_iris if node["type"] == "E" else class_iris).get(node["wco_id"])
        if not iri:
            continue
        iri = iri.replace(SOURCE_BASE, BASE)
        if tag in seen and seen[tag] != iri:
            conflicts.add(tag)
        seen[tag] = iri
    ctx = {"@version": 1.1, "wco": BASE}
    for tag, iri in sorted(seen.items()):
        if tag not in conflicts:
            ctx[tag] = iri
    return ctx, sorted(conflicts)


def write(pkg_key, title, description, by_path, children, root, attr_iris, class_iris,
          version, suffix=""):
    name = f"{pkg_key}{suffix}"
    VERSION = version
    schema = node_schema(root, by_path, children, attr_iris, {})
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{BASE}schemas/{name}-{VERSION}.json",
        "title": title,
        "description": description,
        "x-wco-data-model-version": VERSION,
        **schema,
    }
    (OUT / f"{name}-{VERSION}.json").write_text(json.dumps(schema, indent=1, ensure_ascii=False) + "\n")
    ctx, conflicts = context_for(by_path, attr_iris, class_iris)
    (OUT / f"{name}-{VERSION}-context.jsonld").write_text(
        json.dumps({"@context": ctx}, indent=1, ensure_ascii=False) + "\n")
    return len(by_path), len(ctx) - 2, conflicts


def build(version, attr_iris, class_iris):
    pkg_dir = ROOT / "intermediate" / f"v{version}" / "packages"
    report = {}
    for path in sorted(pkg_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        pkg = json.loads(path.read_text())
        nodes = pkg["nodes"]
        by_path, children = build_tree(nodes)
        _overrides.apply(version, pkg["key"], "base", by_path)
        root = next(n["path"] for n in nodes if n["depth"] == 1)
        n, terms, conflicts = write(pkg["key"], pkg["title"], pkg["description"],
                                    by_path, children, root, attr_iris, class_iris, version)
        report[pkg["key"]] = {"nodes": n, "context_terms": terms, "ambiguous_tags": conflicts,
                              "derived": {}}
        for dip in pkg["derived_packages"]:
            d_by_path, d_children = build_tree(nodes, keep=dip)
            if root not in d_by_path:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", dip).strip("-")
            _overrides.apply(version, pkg["key"], slug, d_by_path)
            dn, dterms, _ = write(pkg["key"], f"{pkg['title']} — {dip}",
                                  f"The {dip} derived information package: the subset of "
                                  f"{pkg['title']} it uses.",
                                  d_by_path, d_children, root, attr_iris, class_iris, version,
                                  suffix=f"-{slug}")
            report[pkg["key"]]["derived"][slug] = dn
    total = sum(1 + len(r["derived"]) for r in report.values())
    print(f"  {version}: {total} schemas and contexts "
          f"({sum(r['nodes'] for r in report.values())} positions)")
    return report


def main():
    OUT.mkdir(exist_ok=True)
    attr_iris, class_iris = property_iris()
    versions = ([_release.version(_release.release_dir())] if os.environ.get("WCO_RELEASE")
                else [_release.version(r) for r in _release.releases()])
    reports = {v: build(v, attr_iris, class_iris) for v in versions}
    path = OUT / "build-report.json"
    existing = json.loads(path.read_text()) if path.exists() and "releases" in path.read_text() else {}
    (OUT / "build-report.json").write_text(
        json.dumps({"releases": reports}, indent=1, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
