#!/usr/bin/env python3
"""Stage D, third part: a browsable view of each message.

A schema is the contract and is not meant to be read. This builds, for every Information Package and
every derived package, the two things a reader needs instead: a compact tree of the message that a
browser can walk, and a conceptual diagram of its classes.

The tree is deduplicated - names, definitions and code list names are pooled into one string table
and referenced by index - because the Declaration package repeats the same 243 classes over 1,847
positions, and sending each one again would make the file ten times the size for no extra meaning.

    python3 scripts/build_package_views.py

Writes views/v<release>/<package>/<message>/tree.json, views/manifest.json, and a .puml per
message per release in diagrams/, rendered to .svg when plantuml is on the path.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import rdflib
from rdflib.namespace import OWL, RDF, SKOS

import _release  # noqa: E402

from build_schemas import SOURCE_BASE, build_tree, clean_tag

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONT, VIEWS, DIAGRAMS = ROOT / "ontology", ROOT / "views", ROOT / "diagrams"
PKG_SLUG = {"bip-dec": "declarations", "bip-lpco": "licences-and-permits",
            "aip": "additional", "mdip": "meta-data"}
# How many classes a conceptual diagram will carry before it stops being a picture and becomes a
# wall. Past this it stops descending, and the page says what sits below.
DIAGRAM_MAX = 48
# A root with more direct classes than this is a fan rather than a tree: graphviz lays them out in
# one rank, and the result is 8,000 pixels wide or 4,000 tall. Those are drawn by module instead.
TOP_MAX = 16


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def vocabulary_index():
    """Three lookups from the published vocabulary: attribute ID to property, class ID to class, and
    property to the concept scheme it ranges at, so a node in a message can point at the term that
    defines it and at the list its values come from."""
    g = rdflib.Graph()
    for f in sorted(ONT.glob("*.ttl")):
        g.parse(f, format="turtle")
    wco = rdflib.Namespace(SOURCE_BASE)
    schema_ns = rdflib.Namespace("https://schema.org/")
    schemes = set(g.subjects(RDF.type, SKOS.ConceptScheme))
    attrs, ranges = {}, {}
    for kind in (OWL.DatatypeProperty, OWL.ObjectProperty):
        for s in g.subjects(RDF.type, kind):
            for attr_id in g.objects(s, wco.attributeId):
                attrs.setdefault(str(attr_id), str(s))
            for r in g.objects(s, schema_ns.rangeIncludes):
                if r in schemes:
                    ranges.setdefault(str(s), str(r))
    classes, modules = {}, {}
    for s in g.subjects(RDF.type, OWL.Class):
        module = next((str(o).rsplit("/", 1)[-1] for o in g.objects(s, rdflib.RDFS.isDefinedBy)), "")
        for class_id in g.objects(s, wco.classId):
            classes.setdefault(str(class_id), str(s))
            modules.setdefault(str(class_id), module)
    labels = {str(s): str(o) for s in schemes for o in g.objects(s, rdflib.RDFS.label)}
    return attrs, classes, ranges, labels, modules


class Strings:
    """A string table. Repeated names and definitions are stored once."""

    def __init__(self):
        self.items, self.index = [], {}

    def __call__(self, text):
        if not text:
            return -1
        i = self.index.get(text)
        if i is None:
            i = self.index[text] = len(self.items)
            self.items.append(text)
        return i


def cardinality(node):
    """The root of a message carries no occurrence of its own: it is the message."""
    if node.get("min") is None and node.get("max") is None:
        return ""
    lo = node.get("min") or "0"
    hi = (node.get("max") or "1").lower()
    return f"{lo}..{'*' if hi == 'unbounded' else hi}"


def build_view(by_path, children, root, vocab):
    attrs, classes, ranges, scheme_labels, _modules = vocab
    s = Strings()
    stats = {"nodes": 0, "classes": 0, "elements": 0, "repeating": 0, "required": 0,
             "maxDepth": 0, "bound": 0, "unbound": 0, "coded": 0}

    def walk(path, depth):
        n = by_path[path]
        stats["nodes"] += 1
        stats["maxDepth"] = max(stats["maxDepth"], depth)
        is_class = n["type"] == "C"
        stats["classes" if is_class else "elements"] += 1
        if (n.get("max") or "").lower() == "unbounded":
            stats["repeating"] += 1
        if (n.get("min") or "0") not in ("0", "", None):
            stats["required"] += 1
        out = {
            "s": path.rsplit("/", 1)[-1],
            "n": s(n.get("name")),
            "d": s(n.get("definition")),
            "t": n["type"],
            "c": cardinality(n),
        }
        tag = clean_tag(n.get("json_tag"), path)
        if tag:
            out["g"] = tag
        xml_tag = clean_tag(n.get("xml_tag"), path)
        if xml_tag:
            out["x"] = xml_tag
        if n.get("format"):
            out["f"] = n["format"]
        if n.get("remark"):
            out["r"] = s(n["remark"])
        for key in ("wco_id", "uci", "seq"):
            if n.get(key):
                out[{"wco_id": "w", "uci": "u", "seq": "q"}[key]] = n[key]
        iri = (classes if is_class else attrs).get(n.get("wco_id") or "")
        if iri:
            out["v"] = iri
            stats["bound"] += 1
        else:
            stats["unbound"] += 1
        scheme = ranges.get(iri or "")
        if scheme:
            out["l"], out["ln"] = scheme, s(scheme_labels.get(scheme))
            stats["coded"] += 1
        elif n.get("code_list"):
            out["ln"] = s(n["code_list"])
            stats["coded"] += 1
        if n.get("used_by"):
            out["ub"] = [slugify(x) for x in n["used_by"]]
        if n.get("source"):
            out["src"] = f'{n["source"]["sheet"]}:{n["source"]["row"]}'
        kids = children.get(path, [])
        if kids:
            out["k"] = [walk(k, depth + 1) for k in kids]
            out["nd"] = sum(1 for k in kids if by_path[k]["type"] != "C")
            out["nc"] = sum(1 for k in kids if by_path[k]["type"] == "C")
        return out

    tree = walk(root, 1)
    return {"strings": s.items, "root": tree, "stats": stats}


HEADER = [
    "@startuml", "hide circle", "hide empty members", "hide stereotype",
    "skinparam shadowing false", "skinparam defaultFontName Helvetica",
    "skinparam defaultFontSize 12", "skinparam nodesep 10", "skinparam ranksep 35",
    "skinparam packageStyle rectangle",
    "skinparam class {", "  BackgroundColor #FFFFFF", "  BorderColor #0B4EA2",
    "  ArrowColor #5B6B7C", "  FontColor #14202E", "}",
    "skinparam class<<root>> {", "  BackgroundColor #0B4EA2", "  FontColor #FFFFFF",
    "  BorderColor #083A7A", "}",
    "skinparam class<<more>> {", "  BackgroundColor #F6F9FC", "  BorderColor #9FB3C8", "}",
]


def puml(title, by_path, children, root, modules):
    """A conceptual view of the message: classes only, no elements.

    Two shapes, because one does not fit both. A message whose top level is small enough to draw is
    drawn as it is, class by class, as deep as stays readable. The Declaration's top level is 67
    classes, which graphviz lays out as a single row 8,000 pixels wide, so that one is drawn a level
    up: the root and the vocabulary modules its top-level classes belong to, each box listing them.
    The grouping is real metadata rather than a presentational convenience, and the page carries the
    same information as a table for anyone the picture does not serve.
    """
    def class_kids(path):
        return [k for k in children.get(path, []) if by_path[k]["type"] == "C"]

    def nested(path):
        return sum(1 + nested(k) for k in class_kids(path))

    def elements(path):
        return sum(1 for k in children.get(path, []) if by_path[k]["type"] != "C")

    top = class_kids(root)
    if len(top) > TOP_MAX:
        return puml_by_module(title, by_path, root, top, modules), 1 + len({
            modules.get(by_path[p].get("wco_id") or "", "") for p in top}), True

    # The root and its own classes are always shown: that is the shape of the message, and a
    # diagram without it says nothing. Further levels are added only while the picture holds.
    levels, frontier = [[root]], top
    while frontier:
        levels.append(frontier)
        nxt = [k for p in frontier for k in class_kids(p)]
        if not nxt or sum(len(l) for l in levels) + len(nxt) > DIAGRAM_MAX:
            break
        frontier = nxt
    shown = [p for level in levels for p in level]
    drawn = set(shown)
    cut = len(shown) < 1 + nested(root)

    ids = {p: f"C{i}" for i, p in enumerate(shown)}
    lines = list(HEADER) + ["left to right direction", f"title {title}"]
    for p in shown:
        own, below = elements(p), nested(p)
        hidden = below > 0 and not any(k in drawn for k in class_kids(p))
        stereo = " <<root>>" if p == root else (" <<more>>" if hidden else "")
        body = []
        if own:
            body.append(f"{own} element{'s' if own != 1 else ''}")
        if hidden:
            body.append(f"{below} class{'es' if below != 1 else ''} below")
        inner = (" {\n  " + "\n  ".join(body) + "\n}") if body else ""
        lines.append(f'class "{by_path[p]["name"]}" as {ids[p]}{stereo}{inner}')
    for p in shown:
        for k in class_kids(p):
            if k in ids:
                lines.append(f'{ids[p]} *-- "{cardinality(by_path[k])}" {ids[k]}')
    if cut:
        lines += ["note as N", "  Classes only, to the depth that stays readable.",
                  "  A shaded box has further classes inside it.", "end note"]
    lines.append("@enduml")
    return "\n".join(lines) + "\n", len(shown), cut


def puml_by_module(title, by_path, root, top, modules):
    """The top level of a large message, grouped by the vocabulary module each class belongs to."""
    groups = {}
    for p in top:
        groups.setdefault(modules.get(by_path[p].get("wco_id") or "", "unassigned"), []).append(p)
    lines = list(HEADER) + [
        f"title {title}  —  top level by vocabulary module",
        f'class "{by_path[root]["name"]}" as ROOT <<root>>',
    ]
    for i, (module, paths) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
        names = "\n  ".join(sorted(by_path[p]["name"] for p in paths))
        lines.append(f'class "{module} ({len(paths)})" as M{i} {{\n  {names}\n}}')
        lines.append(f"ROOT *-- M{i}")
    lines += ["note as N", "  Each box is one vocabulary module and lists the top-level",
              "  classes of this message that belong to it.", "end note", "@enduml"]
    return "\n".join(lines) + "\n"


def render_all(paths):
    """One plantuml invocation for every diagram.

    Each invocation starts a JVM, which costs about two seconds; at 106 diagrams that was most of
    the build. Rendering them in one call takes the same work down to a single start.
    """
    if not paths or not shutil.which("plantuml"):
        return set()
    subprocess.run(["plantuml", "-tsvg", "-nometadata"] + [str(p) for p in paths], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {p for p in paths if p.with_suffix(".svg").exists()}


def build(version, vocab, names, pkg_names, pending):
    pkg_dir = ROOT / "intermediate" / f"v{version}" / "packages"
    entries = {}
    for path in sorted(pkg_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        pkg = json.loads(path.read_text())
        key, nodes = pkg["key"], pkg["nodes"]
        pslug = PKG_SLUG[key]
        entry = {"key": key, "slug": pslug, "title": pkg_names.get(key, pkg["title"]),
                 "description": pkg["description"], "source": pkg["source"], "messages": {}}

        work = [(None, pkg["title"], None)]
        work += [(slugify(d), d, pkg["derived_package_groups"].get(d, ""))
                 for d in pkg["derived_packages"]]
        for mslug, mtitle, group in work:
            by_path, children = build_tree(nodes, keep=None if mslug is None else mtitle)
            root = next((n["path"] for n in nodes if n["depth"] == 1), None)
            if root not in by_path:
                continue
            view = build_view(by_path, children, root, vocab)
            name = mslug or "base"
            display = names.get(mslug, mtitle) if mslug else pkg_names.get(key, mtitle)
            out = VIEWS / f"v{version}" / pslug / name
            out.mkdir(parents=True, exist_ok=True)
            view.update({"package": key, "message": name, "title": display, "version": version})
            (out / "tree.json").write_text(
                json.dumps(view, ensure_ascii=False, separators=(",", ":")) + "\n")

            diagram = f"v{version}-{pslug}-{name}"
            text, boxes, cut = puml(f"{display} {version}", by_path, children, root, vocab[4])
            (DIAGRAMS / f"{diagram}.puml").write_text(text)
            pending.append(DIAGRAMS / f"{diagram}.puml")
            entry["messages"][name] = {
                "slug": name, "title": display, "group": group,
                "derived": mslug is not None,
                "schema": f"{key}-{mslug}-{version}.json" if mslug else f"{key}-{version}.json",
                "context": (f"{key}-{mslug}-{version}-context.jsonld" if mslug
                            else f"{key}-{version}-context.jsonld"),
                "diagram": f"{diagram}.svg",
                "diagram_boxes": boxes, "diagram_cut": cut,
                "stats": view["stats"],
                "top_level": [
                    {"name": by_path[p]["name"], "path": p, "type": by_path[p]["type"],
                     "card": cardinality(by_path[p]),
                     "definition": by_path[p].get("definition") or "",
                     "below": sum(1 for q in by_path if q.startswith(p + "/"))}
                    for p in children.get(root, [])
                ],
            }
        entries[key] = entry
    print(f"  {version}: {sum(len(e['messages']) for e in entries.values())} messages")
    return entries


def main():
    vocab = vocabulary_index()
    # The workbook names a derived package in column-heading shorthand ("mar. api"). The readable
    # name lives with the rest of the package metadata, so the diagram carries that instead.
    meta = json.loads((ROOT / "docs" / "derived-packages.json").read_text())
    names = {k: v.get("name", k) for k, v in meta["derived"].items()}
    pkg_names = {k: v.get("title", k) for k, v in meta["packages"].items()}

    VIEWS.mkdir(exist_ok=True)
    DIAGRAMS.mkdir(exist_ok=True)
    versions = ([_release.version(_release.release_dir())] if os.environ.get("WCO_RELEASE")
                else [_release.version(r) for r in _release.releases()])
    pending = []
    manifest = {v: build(v, vocab, names, pkg_names, pending) for v in versions}
    drawn = render_all(pending)
    if len(drawn) < len(pending):
        missing = {p.with_suffix(".svg").name for p in pending} - {
            p.with_suffix(".svg").name for p in drawn}
        for release in manifest.values():
            for pkg in release.values():
                for entry in pkg["messages"].values():
                    if entry["diagram"] in missing:
                        entry["diagram"] = None
    print(f"  {len(drawn)} of {len(pending)} diagrams rendered"
          + ("" if len(drawn) == len(pending) else " (plantuml not found, or a diagram failed)"))
    (VIEWS / "manifest.json").write_text(
        json.dumps({"releases": manifest}, indent=1, ensure_ascii=False) + "\n")
    print(f"  {len(versions)} releases in views/manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
