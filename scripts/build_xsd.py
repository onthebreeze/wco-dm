#!/usr/bin/env python3
"""Stage D, fourth part: the WCO XML schemas, generated from the same source as everything else.

WCO publishes an XML schema for each of its messages, produced today by a commercial modelling tool
from a model this repository does not have. This script produces those schemas from the workbooks
instead, and scripts/compare_xsd.py checks the result against what WCO published. Where the two
agree, the tool is not the only way to get the artefact.

Two files per message, as WCO publishes them:

    <Name>_4p3p0.xsd                                    the element structure
    <Name>_4p3p0_urn_wco_datamodel_WCO_<Name>_DS_4.xsd  one type per class and attribute

The structure file imports the type file by name, so the two sit in the same directory.

    python3 scripts/build_xsd.py                 # every release
    WCO_RELEASE=v4.3.0 python3 scripts/build_xsd.py
"""
import json
import os
import pathlib
import re
import sys
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _overrides  # noqa: E402
import _release  # noqa: E402
from build_schemas import clean_tag  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "schemas" / "xsd"
XSD = "http://www.w3.org/2001/XMLSchema"

# The imports a type file needs, and the attribute types that need them. These four are UN/CEFACT
# and IANA publications included in WCO's own download package; they are referenced exactly as WCO
# references them and are not reproduced here.
IMPORTS = {
    "clm63055": ("urn:un:unece:uncefact:codelist:standard:UNECE:AgencyIdentificationCode:D23A",
                 "urn_un_unece_uncefact_codelist_standard_UNECE_AgencyIdentificationCode_D23A"),
    "clmIANAMIMEMediaType": ("urn:un:unece:uncefact:codelist:standard:IANA:MIMEMediaType:2013-07-23",
                             "urn_un_unece_uncefact_codelist_standard_IANA_MIMEMediaType_2013-07-23"),
    "clm60133": ("urn:un:unece:uncefact:codelist:standard:UNECE:CharacterSetEncodingCode:40106",
                 "urn_un_unece_uncefact_codelist_standard_UNECE_CharacterSetEncodingCode_40106"),
    "clmIANACharacterSetCode": ("urn:un:unece:uncefact:codelist:standard:IANA:CharacterSetCode:2013-01-23",
                                "urn_un_unece_uncefact_codelist_standard_IANA_CharacterSetCode_2013-01-23"),
}

# A coded attribute restricts to a named content type when its values belong to a standard list,
# and takes xs:token directly when the list is the implementer's own or WCO's. The register names
# the first kind by its authority, which is what this matches.
STANDARD_LIST = re.compile(r"^\s*(UN/EDIFACT|ISO\b|UN/LOCODE)", re.IGNORECASE)


def version_token(version):
    return version.replace(".", "p")


def indent(depth):
    return "  " * depth


def documentation(lines, depth):
    """One annotation carrying what the model says about a position.

    WCO's own schemas carry fifty of these per element, most of them the modelling tool's change
    history: DMR numbers, former names, export settings. None of that is in the workbooks and none
    of it is invented here. What is kept is what an implementer reading the schema needs.
    """
    kept = [(src, text) for src, text in lines if text]
    if not kept:
        return ""
    out = [f"{indent(depth)}<xs:annotation>"]
    for src, text in kept:
        out.append(f"{indent(depth + 1)}<xs:documentation source={quoteattr(src)}>"
                   f"{escape(str(text))}</xs:documentation>")
    out.append(f"{indent(depth)}</xs:annotation>")
    return "\n".join(out) + "\n"


def occurs(node):
    """minOccurs and maxOccurs, written only where they differ from the default of exactly one."""
    lo = node.get("min")
    hi = (node.get("max") or "").lower()
    out = ""
    if lo is not None and str(lo) != "1":
        out += f' minOccurs="{escape(str(lo))}"'
    if hi and hi != "1":
        out += f' maxOccurs="{"unbounded" if hi == "unbounded" else escape(hi)}"'
    return out


def tag_of(node):
    """The element name. A handful of positions carry no XML tag in the workbook, so the last
    segment of the model path stands in, capitalised the way WCO capitalises tags."""
    tag = clean_tag(node.get("xml_tag"), node.get("path"))
    if tag:
        return tag
    tail = (node.get("path") or "").rsplit("/", 1)[-1] or node.get("name") or "Unnamed"
    return tail[:1].upper() + tail[1:]


def structure(message, nodes, children, root_path, attrs, annotate=True):
    name, version = message["name"], message["version"]
    ns = f"urn:wco:datamodel:WCO:{name}:4"
    ds = f"urn:wco:datamodel:WCO:{name}_DS:4"
    ds_file = f"{name}_{version_token(version)}_urn_wco_datamodel_WCO_{name}_DS_4.xsd"
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<xs:schema xmlns="{ns}"',
        f'    xmlns:xs="{XSD}"',
        f'    xmlns:ds="{ds}"',
        f'    targetNamespace="{ns}"',
        '    elementFormDefault="qualified">',
        f'  <xs:import namespace="{ds}" schemaLocation="{ds_file}"/>',
    ]

    def element(path, depth, root=False):
        node = nodes[path]
        tag = message["root"] if root else tag_of(node)
        kids = children.get(path, [])
        attr = attrs.get((node.get("_class"), node.get("wco_id")))
        lines = []
        if annotate:
            lines = documentation([
                ("Dictionary Entry Name", (attr or {}).get("dictionary_entry_name")),
                ("Definition", node.get("definition")),
                ("Remark", node.get("remark")),
                ("WCO ID", node.get("wco_id")),
                ("Unique Position ID", node.get("uci")),
                ("Format", node.get("format")),
                ("Code List", node.get("code_list")),
            ], depth + 1)
        if kids:
            out.append(f'{indent(depth)}<xs:element name="{escape(tag)}"{"" if root else occurs(node)}>')
            if lines:
                out.append(lines.rstrip("\n"))
            out.append(f"{indent(depth + 1)}<xs:complexType>")
            out.append(f"{indent(depth + 2)}<xs:sequence>")
            for child in kids:
                element(child, depth + 3)
            out.append(f"{indent(depth + 2)}</xs:sequence>")
            out.append(f"{indent(depth + 1)}</xs:complexType>")
            out.append(f"{indent(depth)}</xs:element>")
            return
        type_name = (attr or {}).get("named_complex_type")
        typed = f' type="ds:{escape(type_name)}"' if type_name else ""
        if lines:
            out.append(f'{indent(depth)}<xs:element name="{escape(tag)}"{typed}{occurs(node)}>')
            out.append(lines.rstrip("\n"))
            out.append(f"{indent(depth)}</xs:element>")
        else:
            out.append(f'{indent(depth)}<xs:element name="{escape(tag)}"{typed}{occurs(node)}/>')

    element(root_path, 1, root=True)
    out.append("</xs:schema>")
    return "\n".join(out) + "\n"


def type_body(attr, name, depth=1):
    """The content of one type, from the core data type. One shape per type, as WCO writes them."""
    cdt = (attr.get("core_data_type") or "").strip()
    code_list = attr.get("code_list") or ""
    i, j = indent(depth), indent(depth + 1)
    k = indent(depth + 2)

    if cdt == "Text":
        return (f'{i}<xs:complexType name="{name}">\n{j}<xs:simpleContent>\n'
                f'{k}<xs:extension base="xs:string">\n'
                f'{k}  <xs:attribute name="languageID" type="xs:string" use="optional"/>\n'
                f'{k}</xs:extension>\n{j}</xs:simpleContent>\n{i}</xs:complexType>\n'), set()
    if cdt == "Identifier":
        return (f'{i}<xs:complexType name="{name}">\n{j}<xs:simpleContent>\n'
                f'{k}<xs:extension base="xs:string">\n'
                f'{k}  <xs:attribute name="schemeID" type="xs:token" use="optional"/>\n'
                f'{k}  <xs:attribute name="schemeName" type="xs:string" use="optional"/>\n'
                f'{k}  <xs:attribute name="schemeAgencyID" '
                f'type="clm63055:AgencyIdentificationCodeContentType" use="optional"/>\n'
                f'{k}  <xs:attribute name="schemeAgencyName" type="xs:string" use="optional"/>\n'
                f'{k}  <xs:attribute name="schemeVersionID" type="xs:token" use="optional"/>\n'
                f'{k}  <xs:attribute name="schemeDataURI" type="xs:anyURI" use="optional"/>\n'
                f'{k}  <xs:attribute name="schemeURI" type="xs:anyURI" use="optional"/>\n'
                f'{k}</xs:extension>\n{j}</xs:simpleContent>\n{i}</xs:complexType>\n'), {"clm63055"}
    if cdt == "Code":
        standard = bool(STANDARD_LIST.match(code_list))
        base = f"ds:{name[:-4]}ContentType" if standard else "xs:token"
        extra = ""
        if standard:
            extra = (f'{i}<xs:simpleType name="{name[:-4]}ContentType">\n'
                     f'{j}<xs:restriction base="xs:token"/>\n{i}</xs:simpleType>\n')
        return (extra +
                f'{i}<xs:complexType name="{name}">\n{j}<xs:simpleContent>\n'
                f'{k}<xs:extension base="{base}">\n'
                f'{k}  <xs:attribute name="listID" type="xs:token" use="optional"/>\n'
                f'{k}  <xs:attribute name="listAgencyID" '
                f'type="clm63055:AgencyIdentificationCodeContentType" use="optional"/>\n'
                f'{k}  <xs:attribute name="listAgencyName" type="xs:string" use="optional"/>\n'
                f'{k}  <xs:attribute name="listName" type="xs:string" use="optional"/>\n'
                f'{k}  <xs:attribute name="listVersionID" type="xs:token" use="optional"/>\n'
                f'{k}  <xs:attribute name="name" type="xs:string" use="optional"/>\n'
                f'{k}  <xs:attribute name="languageID" type="xs:string" use="optional"/>\n'
                f'{k}  <xs:attribute name="listURI" type="xs:anyURI" use="optional"/>\n'
                f'{k}  <xs:attribute name="listSchemeURI" type="xs:anyURI" use="optional"/>\n'
                f'{k}</xs:extension>\n{j}</xs:simpleContent>\n{i}</xs:complexType>\n'), {"clm63055"}
    if cdt in ("Date Time", "DateTime"):
        return (f'{i}<xs:complexType name="{name}">\n{j}<xs:choice>\n'
                f'{k}<xs:element name="DateTimeString">\n'
                f'{k}  <xs:complexType>\n{k}    <xs:simpleContent>\n'
                f'{k}      <xs:extension base="xs:string">\n'
                f'{k}        <xs:attribute name="formatCode" type="xs:string" use="required"/>\n'
                f'{k}      </xs:extension>\n{k}    </xs:simpleContent>\n{k}  </xs:complexType>\n'
                f'{k}</xs:element>\n'
                f'{j}</xs:choice>\n{i}</xs:complexType>\n'), set()
    if cdt == "Indicator":
        return (f'{i}<xs:complexType name="{name}">\n{j}<xs:choice>\n'
                f'{k}<xs:element name="IndicatorString">\n'
                f'{k}  <xs:complexType>\n{k}    <xs:simpleContent>\n'
                f'{k}      <xs:extension base="xs:string"/>\n'
                f'{k}    </xs:simpleContent>\n{k}  </xs:complexType>\n{k}</xs:element>\n'
                f'{k}<xs:element name="Indicator" type="xs:boolean"/>\n'
                f'{j}</xs:choice>\n{i}</xs:complexType>\n'), set()
    if cdt == "Measure":
        return (f'{i}<xs:complexType name="{name}">\n{j}<xs:simpleContent>\n'
                f'{k}<xs:extension base="xs:decimal">\n'
                f'{k}  <xs:attribute name="unitCode" type="xs:string" use="optional"/>\n'
                f'{k}</xs:extension>\n{j}</xs:simpleContent>\n{i}</xs:complexType>\n'), set()
    if cdt in ("Quantity",):
        return (f'{i}<xs:complexType name="{name}">\n{j}<xs:simpleContent>\n'
                f'{k}<xs:extension base="xs:decimal">\n'
                f'{k}  <xs:attribute name="unitCode" type="xs:token" use="optional"/>\n'
                f'{k}</xs:extension>\n{j}</xs:simpleContent>\n{i}</xs:complexType>\n'), set()
    if cdt == "Amount":
        return (f'{i}<xs:complexType name="{name}">\n{j}<xs:simpleContent>\n'
                f'{k}<xs:extension base="xs:decimal">\n'
                f'{k}  <xs:attribute name="currencyID" type="xs:token" use="optional"/>\n'
                f'{k}</xs:extension>\n{j}</xs:simpleContent>\n{i}</xs:complexType>\n'), set()
    if cdt in ("Binary Object", "Graphic", "Picture", "Sound", "Video"):
        return (f'{i}<xs:complexType name="{name}">\n{j}<xs:simpleContent>\n'
                f'{k}<xs:extension base="xs:base64Binary">\n'
                f'{k}  <xs:attribute name="format" type="xs:string" use="optional"/>\n'
                f'{k}  <xs:attribute name="mimeCode" '
                f'type="clmIANAMIMEMediaType:MIMEMediaTypeContentType" use="optional"/>\n'
                f'{k}  <xs:attribute name="encodingCode" '
                f'type="clm60133:CharacterSetEncodingCodeContentType" use="optional"/>\n'
                f'{k}  <xs:attribute name="characterSetCode" '
                f'type="clmIANACharacterSetCode:CharacterSetCodeContentType" use="optional"/>\n'
                f'{k}  <xs:attribute name="uri" type="xs:anyURI" use="optional"/>\n'
                f'{k}  <xs:attribute name="filename" type="xs:string" use="optional"/>\n'
                f'{k}</xs:extension>\n{j}</xs:simpleContent>\n{i}</xs:complexType>\n'), {
                    "clmIANAMIMEMediaType", "clm60133", "clmIANACharacterSetCode"}
    # Numeric, and anything the core data type sheet does not name: a decimal.
    #
    # No lower bound. WCO's own schemas are inconsistent about it - Additional Identifier. Sequence.
    # Numeric restricts to zero and above, Communication Meta Data. Sequence. Numeric does not,
    # though both are n..5 and both are a sequence number - so there is no rule to follow, and
    # inventing one would make the generator disagree with half the cases either way.
    return (f'{i}<xs:simpleType name="{name}">\n{j}<xs:restriction base="xs:decimal"/>\n'
            f'{i}</xs:simpleType>\n'), set()


def types(message, nodes, attrs, used):
    name, version = message["name"], message["version"]
    ds = f"urn:wco:datamodel:WCO:{name}_DS:4"
    bodies, needed = [], set()
    for type_name, attr in sorted(used.items()):
        body, imports = type_body(attr, type_name)
        bodies.append(body)
        needed |= imports
    header = ['<?xml version="1.0" encoding="UTF-8"?>', f'<xs:schema xmlns:ds="{ds}"',
              f'    xmlns:xs="{XSD}"']
    for prefix in sorted(needed):
        header.append(f'    xmlns:{prefix}="{IMPORTS[prefix][0]}"')
    header += [f'    targetNamespace="{ds}"', '    elementFormDefault="qualified">']
    for prefix in sorted(needed):
        ns, stem = IMPORTS[prefix]
        header.append(f'  <xs:import namespace="{ns}" '
                      f'schemaLocation="{name}_{version_token(version)}_{stem}.xsd"/>')
    return "\n".join(header) + "\n" + "".join(bodies) + "</xs:schema>\n"


def token(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")


def build(version, meta, dip_meta, pkg_meta):
    out_dir = OUT / f"v{version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    attrs = {}
    for a in json.loads((ROOT / "intermediate" / f"v{version}" / "attributes.json").read_text()):
        if a.get("attr_id"):
            attrs[(a.get("class_name"), a["attr_id"])] = a
    written = []
    pkg_dir = ROOT / "intermediate" / f"v{version}" / "packages"
    for path in sorted(pkg_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        pkg = json.loads(path.read_text())
        all_nodes = pkg["nodes"]
        work = [(None, pkg["title"])] + [(d, d) for d in pkg["derived_packages"]]
        for dip, _title in work:
            keep = None if dip is None else dip
            nodes = {n["path"]: n for n in all_nodes}
            if keep is not None:
                wanted = set()
                for n in all_nodes:
                    if keep in (n["used_by"] or []):
                        parts = n["path"].split("/")
                        for i in range(1, len(parts) + 1):
                            wanted.add("/".join(parts[:i]))
                nodes = {p: n for p, n in nodes.items() if p in wanted}
            if not nodes:
                continue
            root_path = next((n["path"] for n in all_nodes if n["depth"] == 1), None)
            if root_path not in nodes:
                continue
            children = {}
            for p in nodes:
                parent = p.rsplit("/", 1)[0] if "/" in p else None
                children.setdefault(parent, []).append(p)
            for v in children.values():
                v.sort(key=lambda p: int(nodes[p].get("seq") or 0))
            # Which class each element belongs to, which is half the key of its type.
            for p, n in nodes.items():
                parent = nodes.get(p.rsplit("/", 1)[0]) if "/" in p else None
                n["_class"] = parent["name"] if parent else None

            slug = re.sub(r"[^a-z0-9]+", "-", (dip or "base")).strip("-") if dip else "base"
            _overrides.apply(version, pkg["key"], slug, nodes)
            key = f'{pkg["key"]}/{slug}'
            declared = meta.get(key) or {}
            display = (dip_meta.get(slug, {}).get("name") if dip
                       else pkg_meta.get(pkg["key"], {}).get("title")) or pkg["title"]
            message = {
                "name": declared.get("name") or token(display),
                "root": declared.get("root") or tag_of(nodes[root_path]),
                "version": version,
            }
            used = {}
            for n in nodes.values():
                if n["type"] == "E" and not children.get(n["path"]):
                    a = attrs.get((n.get("_class"), n.get("wco_id")))
                    if a and a.get("named_complex_type"):
                        used[a["named_complex_type"]] = a
            stem = f'{message["name"]}_{version_token(version)}'
            (out_dir / f"{stem}.xsd").write_text(
                structure(message, nodes, children, root_path, attrs))
            (out_dir / f'{stem}_urn_wco_datamodel_WCO_{message["name"]}_DS_4.xsd').write_text(
                types(message, nodes, attrs, used))
            written.append((key, message["name"], len(nodes), len(used)))
    print(f"  {version}: {len(written)} message schemas, "
          f"{sum(w[3] for w in written)} types")
    return written


def main():
    schemas = json.loads((ROOT / "docs" / "xml-schemas.json").read_text())
    meta_all = json.loads((ROOT / "docs" / "derived-packages.json").read_text())
    dip_meta, pkg_meta = meta_all["derived"], meta_all["packages"]
    versions = ([_release.version(_release.release_dir())] if os.environ.get("WCO_RELEASE")
                else [_release.version(r) for r in _release.releases()])
    OUT.mkdir(parents=True, exist_ok=True)
    for version in versions:
        by_message = {}
        for message, entry in (schemas.get(version) or {}).items():
            if message.startswith("_unmapped/"):
                continue
            pkg, _, slug = message.rpartition("/")
            key = {"declarations": "bip-dec", "licences-and-permits": "bip-lpco",
                   "additional": "aip", "meta-data": "mdip"}.get(pkg, pkg)
            by_message[f"{key}/{slug}"] = entry
        build(version, by_message, dip_meta, pkg_meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
