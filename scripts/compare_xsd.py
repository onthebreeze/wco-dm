#!/usr/bin/env python3
"""Compare the structures this repository generates against the XML schemas WCO publishes.

The question this answers is whether the published XSDs could be generated from a vocabulary held
in git rather than from the tooling WCO uses now. It is answered by taking each published schema,
reducing it to the set of element paths it defines with their cardinality, and diffing that against
the same message's tree.json.

    python3 scripts/compare_xsd.py                # compare what is cached
    python3 scripts/compare_xsd.py --fetch        # download the schemas first
    python3 scripts/compare_xsd.py --detail mar-api

The schemas are large - the Declaration is 50MB - so they are cached outside the repository and not
committed. docs/xml-schemas.json records where each one lives.
"""
import json
import os
import pathlib
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = pathlib.Path(os.environ.get("WCO_XSD_CACHE", "/tmp/wco-xsd"))
XS = "{http://www.w3.org/2001/XMLSchema}"
VERSION = "4.3.0"


def fetch(entry):
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / entry["file"]
    if target.exists():
        return target
    print(f"  downloading {entry['file']}")
    with urllib.request.urlopen(entry["url"], timeout=120) as r:
        target.write_bytes(r.read())
    return target


def xsd_paths(path, root_name=None):
    """Every element position the schema defines, as a path, with its cardinality.

    The schemas nest anonymous complex types rather than naming and reusing them, so the element
    tree is the information tree and nothing has to be resolved.
    """
    out = {}

    def walk(node, prefix):
        for child in node:
            if child.tag == XS + "element" and child.get("name"):
                name = child.get("name")
                here = f"{prefix}/{name}" if prefix else name
                out[here] = (child.get("minOccurs", "1"), child.get("maxOccurs", "1"))
                walk(child, here)
            else:
                walk(child, prefix)

    walk(ET.parse(path).getroot(), "")
    return out


def our_paths(message, root_name=None):
    """The same, from the tree this repository generates. The root element is renamed where the
    published schema renames it, which is the one thing about a schema the workbooks do not say."""
    f = ROOT / "views" / f"v{VERSION}" / message / "tree.json"
    tree = json.loads(f.read_text())
    out = {}

    def walk(node, prefix, is_root=False):
        tag = (root_name if is_root and root_name else node.get("x") or node["s"])
        here = f"{prefix}/{tag}" if prefix else tag
        card = node.get("c") or ""
        lo, hi = (card.split("..") + [""])[:2] if card else ("", "")
        out[here] = (lo, "unbounded" if hi == "*" else hi)
        for child in node.get("k", []):
            walk(child, here)

    walk(tree["root"], "", is_root=True)
    return out


def compare(message, entry):
    x = xsd_paths(fetch(entry))
    o = our_paths(message, entry["root"])
    both = set(x) & set(o)
    card = sorted(p for p in both if p.count("/") and x[p] != o[p])
    return {"message": message, "xsd": len(x), "ours": len(o), "both": len(both),
            "xsd_only": sorted(set(x) - set(o)), "ours_only": sorted(set(o) - set(x)),
            "cardinality": [(p, o[p], x[p]) for p in card]}


def main():
    meta = json.loads((ROOT / "docs" / "xml-schemas.json").read_text())[VERSION]
    wanted = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    results = []
    for message, entry in sorted(meta.items()):
        if message.startswith("_unmapped/"):
            continue
        if wanted and wanted not in message:
            continue
        if not (CACHE / entry["file"]).exists() and "--fetch" not in sys.argv:
            print(f"  {message}: not cached, run with --fetch")
            continue
        results.append(compare(message, entry))

    print(f"{'message':36}{'positions':>10}{'matched':>9}{'missing':>9}{'extra':>7}"
          f"{'cardinality':>13}")
    for r in results:
        print(f"{r['message']:36}{r['xsd']:>10}{r['both']:>9}{len(r['ours_only']):>9}"
              f"{len(r['xsd_only']):>7}{len(r['cardinality']):>13}")

    exact = [r for r in results if not r["ours_only"] and not r["xsd_only"]]
    perfect = [r for r in exact if not r["cardinality"]]
    print(f"\n{len(exact)} of {len(results)} reproduce the element tree exactly; "
          f"{len(perfect)} also reproduce every cardinality.")

    if "--detail" in sys.argv:
        for r in results:
            if not (r["ours_only"] or r["xsd_only"] or r["cardinality"]):
                continue
            print(f"\n{r['message']}")
            for p in r["ours_only"][:10]:
                print(f"    only here : {p}")
            for p in r["xsd_only"][:10]:
                print(f"    only WCO  : {p}")
            for p, ours, theirs in r["cardinality"][:10]:
                print(f"    {p}\n        workbook {ours[0]}..{ours[1]}   schema {theirs[0]}..{theirs[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
