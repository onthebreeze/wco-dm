#!/usr/bin/env python3
"""Stage A: the two WCO workbooks of one release to a normalised intermediate.

Everything downstream reads the intermediate rather than the spreadsheets, so there is exactly one
place where the source layout is understood. Every record carries the file, sheet and row it came
from, which is what makes a published statement traceable back to a cell.

Columns are found by heading rather than by position, because the four releases do not agree on
layout. The Library also carries two things this extractor used to ignore and now keeps: the
superclass each class belongs to (SC4 Party, SC3 Location, SC2 GovernmentAgency, SC1 RootDocument,
SC5 TransportMeans) and the superclass element each attribute realises (S009 identification is one
element realised by 81 differently-named attributes). That is the model's own statement that a
Carrier is a Party, and that Agent identifier and Carrier identifier are the same thing.

    python3 scripts/extract.py                      # the newest release
    WCO_RELEASE=v4.1.0 python3 scripts/extract.py   # a named one
    python3 scripts/extract.py --all                # every release in raw-data/
"""
import json
import pathlib
import re
import sys

import openpyxl

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _release  # noqa: E402
from _sheet import Headings  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The six superclass-usage flags, in the order the sheet lays them out. Every library row carries
# exactly one (a single row carries two, which is reported rather than hidden).
SUPERCLASSES = ["NONE", "DOC", "GOV", "LOC", "PAR", "TRA"]
MODULE_OF = {
    "NONE": "core",
    "DOC": "document",
    "GOV": "government",
    "LOC": "location",
    "PAR": "party",
    "TRA": "transport",
}

# Each field, as the headings that have named it across the four releases. The first one found
# wins, so adding a release that renames a column is one more alternative here.
LIB_FIELDS = {
    "uml_path": ("UML Model Path", "XPath"),
    "class_id": ("Class ID",), "class_name": ("Class Name",),
    "attr_id": ("Attr. ID",), "attr_name": ("Attribute Name",),
    "definition": ("Definition",), "format": ("Format",), "code_list": ("Code List",),
    "code_id": ("Code ID",), "code_description": ("Code Description",),
    "core_data_type": ("Core Data Type", "CDT"), "uid": ("UID",),
    "dictionary_entry_name": ("Dictionary Entry Name",),
    "named_complex_type": ("Named Complex Type",),
    "xml_tag": ("XML Tag Name",), "json_tag": ("JSON Tag Name",),
    "seq_no": ("Seq. No.",), "type": ("Type",),
}
# These repeat elsewhere in the sheet, so they are qualified by the block they sit under.
LIB_GROUPED = {
    "superclass_id": (("ID",), "SuperClass"),
    "superclass_name": (("Class Name",), "SuperClass"),
    "superclass_element_id": (("ID",), "SuperClass Element"),
    "superclass_element_name": (("Element Name",), "SuperClass Element"),
}

OIS_FIELDS = {
    "uml_path": ("UML Model Path", "XPath"),
    "id": ("ID",), "name": ("Name",), "definition": ("Definition",), "remarks": ("Remarks",),
    "format": ("Format",), "code_list": ("Code List",), "type": ("Type",),
    "seq_no": ("Seq. No.",), "attr_upi": ("Attr. UPI", "Attribute UPI"),
    "cis_upi": ("CIS UPI",),
    "dec_uci": ("DEC UCI",), "ig_uci": ("IG UCI",), "lpco_uci": ("LPCO UCI",),
    "mdip_uci": ("MDIP UCI",), "res_uci": ("RES UCI",),
}

PACKAGES = {"dec_uci": "DEC", "ig_uci": "AIP-IG", "lpco_uci": "LPCO", "mdip_uci": "MDIP", "res_uci": "AIP-RES"}


def clean(v):
    """Cell to trimmed string, or None. Newlines inside a cell are meaningful in the code-list
    sheets, so they survive; surrounding whitespace does not."""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def source(file, sheet, row):
    return {"file": file, "sheet": sheet, "row": row}


def read_library(raw, lib):
    wb = openpyxl.load_workbook(raw / lib, read_only=True, data_only=True)

    classes, attributes, unflagged, multi_flagged = {}, [], [], []
    ws = wb["DataSet 1.2, 1.3, 1.4"]
    h = Headings(ws, header_row=2, group_rows=(1,))
    cols = {k: h.find(*names) for k, names in LIB_FIELDS.items()}
    cols.update({k: h.find(*names, group=group) for k, (names, group) in LIB_GROUPED.items()})
    missing = [k for k in ("class_id", "class_name", "attr_id", "attr_name", "definition")
               if cols[k] is None]
    if missing:
        raise SystemExit(f"{lib}: library sheet has no column for {missing}")

    for n, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        def get(k, row=row):
            i = cols.get(k)
            return clean(row[i]) if i is not None and i < len(row) else None
        class_name = get("class_name")
        if not class_name:
            continue
        flags = [SUPERCLASSES[i] for i in range(6) if clean(row[i])]
        if not flags:
            unflagged.append(n)
        elif len(flags) > 1:
            multi_flagged.append({"row": n, "flags": flags, "name": get("dictionary_entry_name")})
        module = MODULE_OF.get(flags[0], "core") if flags else "core"

        if class_name not in classes:
            classes[class_name] = {
                "class_id": get("class_id"), "class_name": class_name, "module": module,
                "uml_path": get("uml_path"), "definition": None,
                "superclass_id": get("superclass_id"), "superclass": get("superclass_name"),
                "source": source(lib, ws.title, n),
            }
        elif not classes[class_name]["superclass_id"] and get("superclass_id"):
            # The superclass is stated on the attribute rows as well as the class row, and a
            # release does not always put it on both.
            classes[class_name]["superclass_id"] = get("superclass_id")
            classes[class_name]["superclass"] = get("superclass_name")
        if not get("attr_id"):
            # A class row: its definition sits on the row that names no attribute.
            if get("definition") and not classes[class_name]["definition"]:
                classes[class_name]["definition"] = get("definition")
            continue

        attributes.append({
            "class_id": get("class_id"), "class_name": class_name, "attr_id": get("attr_id"),
            "attr_name": get("attr_name"), "definition": get("definition"), "format": get("format"),
            "code_list": get("code_list"), "core_data_type": get("core_data_type"),
            "dictionary_entry_name": get("dictionary_entry_name"),
            "named_complex_type": get("named_complex_type"),
            "xml_tag": get("xml_tag"), "json_tag": get("json_tag"),
            "uml_path": get("uml_path"), "module": module, "type": get("type"),
            "superclass_id": get("superclass_id"), "superclass": get("superclass_name"),
            "superclass_element_id": get("superclass_element_id"),
            "superclass_element": get("superclass_element_name"),
            "source": source(lib, ws.title, n),
        })

    data_types = []
    ws = wb["DataSet 1.5"]
    for n, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        name, attr = clean(row[1]), clean(row[2])
        if not name:
            continue
        data_types.append({
            "seq": clean(row[0]), "name": name, "attribute": attr,
            "code_list": clean(row[3]), "remarks": clean(row[4]),
            "source": source(lib, ws.title, n),
        })

    code_lists = []
    ws = wb["DataSet 1.6"]
    for n, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        name = clean(row[1])
        if not name:
            continue
        ids = clean(row[3])
        descs = clean(row[4])
        # Where WCO owns the list, the codes and their descriptions are newline-separated in one
        # cell each. Where it does not, both cells are empty and the basis names the external list.
        codes = []
        if ids:
            id_lines = [x.strip() for x in ids.split("\n") if x.strip()]
            desc_lines = [x.strip() for x in (descs or "").split("\n")]
            for i, code in enumerate(id_lines):
                codes.append({"code": code, "description": desc_lines[i] if i < len(desc_lines) else None})
        code_lists.append({
            "seq": clean(row[0]), "name": name, "basis": clean(row[2]),
            "codes": codes, "external": not codes,
            "source": source(lib, ws.title, n),
        })

    wb.close()
    return classes, attributes, data_types, code_lists, unflagged, multi_flagged


def read_ois(raw, ois):
    wb = openpyxl.load_workbook(raw / ois, read_only=True, data_only=True)
    ws = wb["OIS"]
    h = Headings(ws, header_row=3, group_rows=(1, 2))
    cols = {k: h.find(*names) for k, names in OIS_FIELDS.items()}
    occurrences = []
    for n, row in enumerate(ws.iter_rows(min_row=4, values_only=True), start=4):
        def get(k, row=row):
            i = cols.get(k)
            return clean(row[i]) if i is not None and i < len(row) else None
        if not get("id"):
            continue
        packages = [label for col, label in PACKAGES.items() if get(col)]
        occurrences.append({
            "uml_path": get("uml_path"), "id": get("id"), "name": get("name"),
            "definition": get("definition"), "remarks": get("remarks"), "format": get("format"),
            "code_list": get("code_list"), "type": get("type"),
            "packages": packages,
            "positions": {label: get(col) for col, label in PACKAGES.items() if get(col)},
            "source": source(ois, ws.title, n),
        })
    wb.close()
    return occurrences


def extract(release):
    version = _release.version(release)
    lib = _release.workbook("library", release).name
    ois = _release.workbook("ois", release).name
    out = ROOT / "intermediate" / f"v{version}"
    out.mkdir(parents=True, exist_ok=True)

    classes, attributes, data_types, code_lists, unflagged, multi_flagged = read_library(release, lib)
    occurrences = read_ois(release, ois)

    for name, payload in (
        ("classes", sorted(classes.values(), key=lambda c: c["class_name"])),
        ("attributes", attributes),
        ("data-types", data_types),
        ("code-lists", code_lists),
        ("ois-occurrences", occurrences),
    ):
        (out / f"{name}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")

    superclasses = {}
    for c in classes.values():
        if c.get("superclass_id"):
            superclasses.setdefault(c["superclass_id"], c["superclass"])
    elements = {}
    for a in attributes:
        if a.get("superclass_element_id"):
            elements.setdefault(a["superclass_element_id"], a["superclass_element"])

    report = {
        "source": {"library": lib, "ois": ois, "version": version},
        "counts": {
            "classes": len(classes), "attributes": len(attributes),
            "data_types": len(data_types), "code_lists": len(code_lists),
            "code_lists_with_values": sum(1 for c in code_lists if not c["external"]),
            "code_lists_external": sum(1 for c in code_lists if c["external"]),
            "ois_occurrences": len(occurrences),
            "classes_with_a_superclass": sum(1 for c in classes.values() if c.get("superclass_id")),
            "attributes_with_a_superclass_element": sum(
                1 for a in attributes if a.get("superclass_element_id")),
        },
        "superclasses": dict(sorted(superclasses.items())),
        "superclass_elements": dict(sorted(elements.items())),
        "modules": {m: sum(1 for c in classes.values() if c["module"] == m)
                    for m in sorted(set(MODULE_OF.values()))},
        "anomalies": {
            "rows_without_a_superclass_flag": unflagged,
            "rows_with_more_than_one_flag": multi_flagged,
            "classes_without_a_definition": sorted(
                c["class_name"] for c in classes.values() if not c["definition"]
            ),
        },
    }
    (out / "extraction-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    c = report["counts"]
    print(f"  {version}: {c['classes']} classes ({c['classes_with_a_superclass']} with a "
          f"superclass), {c['attributes']} attributes "
          f"({c['attributes_with_a_superclass_element']} with a superclass element), "
          f"{c['code_lists']} code lists, {c['ois_occurrences']} OIS positions")
    return report


def main():
    releases = _release.releases() if "--all" in sys.argv else [_release.release_dir()]
    reports = [extract(r) for r in releases]
    index = {
        "releases": [
            {"version": r["source"]["version"], "date": None,
             "library": r["source"]["library"], "ois": r["source"]["ois"],
             "counts": r["counts"]}
            for r in sorted(reports, key=lambda r: tuple(
                int(n) for n in r["source"]["version"].split(".")))
        ],
    }
    if "--all" in sys.argv:
        # The date is left null until WCO's own publication dates are to hand. The lifecycle works
        # on version alone; a date is an addition to it rather than a prerequisite.
        path = ROOT / "intermediate" / "releases.json"
        path.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
        print(f"  {len(reports)} releases indexed in {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
