#!/usr/bin/env python3
"""Take the cardinality WCO's published XML schemas state, where the workbooks do not state it.

A base package's schema agrees with its workbook on every occurrence. A derived package's does not:
the workbook marks that a position is used by a message, never how often it must appear, so the
published schema is the only statement of obligation that exists. Where the two differ, the schema
is taken as normative and the difference is recorded here with its source, so every artefact this
repository generates - JSON Schema, structure, XML schema and page - says the same thing.

    python3 scripts/import_xsd_cardinality.py          # rewrites docs/cardinality-overrides.json

The schemas are large and are not committed; compare_xsd.py --fetch downloads them first.
"""
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_schemas import build_tree, clean_tag  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = pathlib.Path("/tmp/wco-xsd")
XS = "{http://www.w3.org/2001/XMLSchema}"
PKG_OF = {"declarations": "bip-dec", "licences-and-permits": "bip-lpco",
          "additional": "aip", "meta-data": "mdip"}


def xsd_cardinality(path):
    out = {}

    def walk(node, prefix):
        for child in node:
            if child.tag == XS + "element" and child.get("name"):
                here = f"{prefix}/{child.get('name')}" if prefix else child.get("name")
                out[here] = (child.get("minOccurs", "1"), child.get("maxOccurs", "1"))
                walk(child, here)
            else:
                walk(child, prefix)

    walk(ET.parse(path).getroot(), "")
    return out


def xml_path(path, nodes, root_name):
    parts, p = [], path
    while p:
        node = nodes.get(p)
        if node is None:
            break
        tag = clean_tag(node.get("xml_tag"), node.get("path")) or node["name"]
        parts.append(tag)
        p = p.rsplit("/", 1)[0] if "/" in p else None
    parts = list(reversed(parts))
    if parts and root_name:
        parts[0] = root_name
    return "/".join(parts)


def main():
    schemas = json.loads((ROOT / "docs" / "xml-schemas.json").read_text())
    out = {"_note": ("Cardinality taken from WCO's published XML schemas where it differs from the "
                     "workbook. The workbook's derived-package columns record that a position is "
                     "used by a message, never how often it must appear, so for a derived package "
                     "the schema is the only statement of obligation there is. Keyed by the model "
                     "path, which is what the workbooks use. Rewritten by "
                     "scripts/import_xsd_cardinality.py.")}
    for version, messages in schemas.items():
        if version.startswith("_"):
            continue
        for message, entry in sorted(messages.items()):
            if message.startswith("_unmapped/"):
                continue
            cached = CACHE / entry["file"]
            if not cached.exists():
                print(f"  {message}: {entry['file']} not cached, skipping")
                continue
            pkg_slug, _, slug = message.rpartition("/")
            key = PKG_OF.get(pkg_slug, pkg_slug)
            pkg = json.loads((ROOT / "intermediate" / f"v{version}" / "packages"
                              / f"{key}.json").read_text())
            dip = None
            if slug != "base":
                dip = next((d for d in pkg["derived_packages"]
                            if d.replace(" ", "-").replace(".", "").lower().strip("-") in
                            (slug, slug.replace("-", ""))), None)
                if dip is None:
                    import re
                    dip = next((d for d in pkg["derived_packages"]
                                if re.sub(r"[^a-z0-9]+", "-", d).strip("-") == slug), None)
                if dip is None:
                    print(f"  {message}: no derived package matches")
                    continue
            nodes, _children = build_tree(pkg["nodes"], keep=dip)
            theirs = xsd_cardinality(cached)
            changes = {}
            for path, node in nodes.items():
                xp = xml_path(path, nodes, entry["root"])
                want = theirs.get(xp)
                if not want or path.count("/") == 0:
                    continue
                have = (str(node.get("min") or "0"),
                        (node.get("max") or "1").lower())
                if (want[0], want[1].lower()) != have:
                    changes[path] = {"min": want[0], "max": want[1],
                                     "workbook": {"min": have[0], "max": have[1]}}
            if changes:
                out.setdefault(version, {})[f"{key}/{slug}"] = {
                    "source": entry["url"], "schema": entry["file"], "positions": changes}
                print(f"  {message}: {len(changes)} positions taken from the schema")
    path = ROOT / "docs" / "cardinality-overrides.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    total = sum(len(m["positions"]) for v, ms in out.items() if not v.startswith("_")
                for m in ms.values())
    print(f"  {total} positions recorded in {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
