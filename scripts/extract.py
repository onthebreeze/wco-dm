#!/usr/bin/env python3
"""Stage A: the two WCO workbooks to a normalised intermediate.

Everything downstream reads the intermediate rather than the spreadsheets, so there is exactly one
place where the source layout is understood. Every record carries the file, sheet and row it came
from, which is what makes a published statement traceable back to a cell.

    python3 scripts/extract.py            # writes intermediate/*.json
"""
import json
import pathlib
import re
import sys

import openpyxl

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "raw-data"
OUT = ROOT / "intermediate"

LIB = "1.1 WCO DM LIB V4.3.0.xlsx"
OIS = "WCO DM OIS_V4.3.0.xlsx"

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

# Library columns, by position. Named here so the rest of the file reads as fields rather than
# indexes, and so a change in the workbook layout fails in one obvious place.
LIB_COLS = {
    "uml_path": 6, "class_id": 7, "class_name": 8, "attr_id": 9, "attr_name": 10,
    "definition": 11, "format": 12, "code_list": 13, "code_id": 14, "code_description": 15,
    "core_data_type": 16, "uid": 17, "name": 18, "dictionary_entry_name": 19,
    "named_complex_type": 20, "xml_tag": 21, "json_tag": 22, "seq_no": 27, "type": 28,
}

OIS_COLS = {
    "uml_path": 0, "id": 1, "name": 2, "definition": 3, "remarks": 4, "format": 5,
    "code_list": 6, "cis_upi": 7, "dec_uci": 8, "ig_uci": 9, "lpco_uci": 10, "mdip_uci": 11,
    "res_uci": 12, "attr_upi": 13, "seq_no": 14, "type": 15,
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


def read_library():
    wb = openpyxl.load_workbook(RAW / LIB, read_only=True, data_only=True)

    classes, attributes, unflagged, multi_flagged = {}, [], [], []
    ws = wb["DataSet 1.2, 1.3, 1.4"]
    for n, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        get = lambda k: clean(row[LIB_COLS[k]])
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
                "uml_path": get("uml_path"), "definition": None, "source": source(LIB, ws.title, n),
            }
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
            "source": source(LIB, ws.title, n),
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
            "source": source(LIB, ws.title, n),
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
            "source": source(LIB, ws.title, n),
        })

    wb.close()
    return classes, attributes, data_types, code_lists, unflagged, multi_flagged


def read_ois():
    wb = openpyxl.load_workbook(RAW / OIS, read_only=True, data_only=True)
    ws = wb["OIS"]
    occurrences = []
    for n, row in enumerate(ws.iter_rows(min_row=4, values_only=True), start=4):
        get = lambda k: clean(row[OIS_COLS[k]])
        if not get("id"):
            continue
        packages = [label for col, label in PACKAGES.items() if get(col)]
        occurrences.append({
            "uml_path": get("uml_path"), "id": get("id"), "name": get("name"),
            "definition": get("definition"), "remarks": get("remarks"), "format": get("format"),
            "code_list": get("code_list"), "type": get("type"),
            "packages": packages,
            "positions": {label: get(col) for col, label in PACKAGES.items() if get(col)},
            "source": source(OIS, ws.title, n),
        })
    wb.close()
    return occurrences


def main():
    OUT.mkdir(exist_ok=True)
    classes, attributes, data_types, code_lists, unflagged, multi_flagged = read_library()
    occurrences = read_ois()

    for name, payload in (
        ("classes", sorted(classes.values(), key=lambda c: c["class_name"])),
        ("attributes", attributes),
        ("data-types", data_types),
        ("code-lists", code_lists),
        ("ois-occurrences", occurrences),
    ):
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
        print(f"  {path.relative_to(ROOT)}: {len(payload)} records")

    report = {
        "source": {"library": LIB, "ois": OIS, "version": "4.3.0"},
        "counts": {
            "classes": len(classes), "attributes": len(attributes),
            "data_types": len(data_types), "code_lists": len(code_lists),
            "code_lists_with_values": sum(1 for c in code_lists if not c["external"]),
            "code_lists_external": sum(1 for c in code_lists if c["external"]),
            "ois_occurrences": len(occurrences),
        },
        "modules": {m: sum(1 for c in classes.values() if c["module"] == m) for m in sorted(MODULE_OF.values())},
        "anomalies": {
            "rows_without_a_superclass_flag": unflagged,
            "rows_with_more_than_one_flag": multi_flagged,
            "classes_without_a_definition": sorted(
                c["class_name"] for c in classes.values() if not c["definition"]
            ),
        },
    }
    (OUT / "extraction-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(f"  {(OUT / 'extraction-report.json').relative_to(ROOT)}")
    print(json.dumps(report["counts"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
