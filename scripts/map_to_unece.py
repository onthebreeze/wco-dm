#!/usr/bin/env python3
"""Stage C: candidate SKOS mappings from WCO terms to vocab.unece.org concepts.

The ledger is the CSV, not the TTL. A reviewer edits the decision column, reruns, and the TTL is
regenerated from it, so a human judgement is never overwritten by the next build.

Scoring is deliberately transparent: each signal is named in the evidence column so a reviewer can
see why a candidate was proposed rather than trusting a number.

    UNECE_ONTOLOGY=/path/to/vocab-bsp/ontology python3 scripts/map_to_unece.py
"""
import csv
import difflib
import os
import pathlib
import re
import sys
from collections import defaultdict

import rdflib
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONT, MAP = ROOT / "ontology", ROOT / "mappings"
UNECE_ONT = pathlib.Path(os.environ.get("UNECE_ONTOLOGY", "/Users/stevencapell/gitlab/vocab-bsp/ontology"))
# The vocabulary's TTL carries a test base; the published concepts live here.
UNECE_PUBLISHED = os.environ.get("UNECE_BASE", "https://vocab.unece.org/")
WCO_NS = "https://vocabulary.wcoomd.org/"
LEDGER = MAP / "wco-to-unece.csv"

# Above this a match is proposed as accepted; between the two it is proposed for review; below the
# lower bound it is not written out at all.
ACCEPT, REVIEW = 0.90, 0.42

STOP = {"the", "a", "an", "of", "to", "for", "in", "on", "by", "with", "or", "and", "is", "that",
        "this", "which", "as", "its", "it", "be", "are", "at", "from"}

# WCO ends a property name with its representation term; vocab.unece.org usually does not, so
# tareWeightMeasure and tareWeight are the same concept. The suffix is stripped before comparing.
REPRESENTATION_TERMS = ("Text", "Code", "Identifier", "Measure", "Quantity", "Amount", "Indicator",
                        "DateTime", "Numeric", "Percent", "BinaryObject", "Content")


def words(text):
    return [w for w in re.split(r"[^a-z0-9]+", (text or "").lower()) if w and w not in STOP]


def split_camel(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name or "")


def tokens(term):
    """A term's words for matching. WCO class labels arrive run together (AEOProgramProfile), so
    camel case is split on every label rather than only on the ones that are missing."""
    base = words(split_camel(term["label"] or "") or split_camel(term["local"]))
    for alias in term.get("aliases") or []:
        base += words(split_camel(alias))
    # A code list is named for the concept, not for the fact that it is a list.
    return [w for w in base if w not in ("code", "list", "codes")]


def load_terms(graph, base_filter=None):
    out = []
    kinds = ((OWL.Class, "class"), (OWL.DatatypeProperty, "property"),
             (OWL.ObjectProperty, "property"), (SKOS.ConceptScheme, "code-list"))
    for kind, name in kinds:
        for s in graph.subjects(RDF.type, kind):
            iri = str(s)
            if base_filter and not iri.startswith(base_filter):
                continue
            label = next((str(o) for o in graph.objects(s, RDFS.label)), "")
            definition = next((str(o) for o in graph.objects(s, SKOS.definition)), "")
            out.append({
                "iri": iri, "local": iri.rsplit("/", 1)[-1], "label": label,
                "definition": definition, "kind": name, "aliases": [],
            })
    return out


def name_externals(terms, graph):
    """A code list the WCO register does not hold is named after the reference rather than after
    the concept: the scheme for "UN/EDIFACT code list 4405 OR User codes" is called exactly that,
    which matches nothing. The properties that range at it do have concept names - Document/message
    status code - so those are added as aliases and the matching has something to work with."""
    wco = rdflib.Namespace("https://vocabulary.wcoomd.org/")
    schema = rdflib.Namespace("https://schema.org/")
    by_iri = {t["iri"]: t for t in terms}
    for prop in graph.subjects(schema.rangeIncludes, None):
        pass
    for prop, scheme in graph.subject_objects(schema.rangeIncludes):
        t = by_iri.get(str(scheme))
        if t is None or t["kind"] != "code-list":
            continue
        if next(graph.objects(scheme, wco.codeListOrigin), None) != rdflib.Literal("referenced"):
            continue
        label = next((str(o) for o in graph.objects(prop, RDFS.label)), "")
        local = str(prop).rsplit("/", 1)[-1]
        t.setdefault("users", 0)
        t["users"] += 1
        for alias in (local, label):
            if alias and alias not in t["aliases"]:
                t["aliases"].append(alias)

    # A list that many properties range at is not named by any one of them. "User code list" is
    # the extreme case: it is not a concept at all, it is the register declining to name one, and
    # letting it borrow the name of whichever property happened to be read first produced a
    # confident match to seal-condition-code-list.
    for t in terms:
        if t["kind"] != "code-list":
            continue
        basis = " ".join(str(o).lower() for o in graph.objects(rdflib.URIRef(t["iri"]),
                                                               rdflib.URIRef(WCO_NS + "codeListBasis")))
        if t.get("users", 0) > 2 or not basis or basis.strip().startswith("user code"):
            t["aliases"] = []
    return terms


def list_key(name):
    """A code list's name with the noise removed, for comparing one register's naming with
    another's. DocumentStatusCode, document-status-code-list and "Document Status" all reduce to
    "document status"."""
    out = [w for w in words(split_camel(name or "").replace("-", " "))
           if w not in ("code", "codes", "list")]
    return " ".join(out)


def strip_representation(name):
    for rt in REPRESENTATION_TERMS:
        if len(name) > len(rt) + 2 and name.endswith(rt):
            return name[: -len(rt)]
    return name


def score(a, b):
    """Returns (score, evidence). Signals are additive and named."""
    ev, s = [], 0.0
    al, bl = a["local"].lower(), b["local"].lower()
    sa, sb = strip_representation(a["local"]).lower(), strip_representation(b["local"]).lower()
    if al != bl and sa == sb:
        s += 0.45; ev.append("same name once the representation term is removed")
    if al == bl:
        s += 0.55; ev.append("local name identical")
    elif al.rstrip("s") == bl.rstrip("s"):
        s += 0.45; ev.append("local name identical but for plural")

    la, lb = " ".join(tokens(a)), " ".join(tokens(b))
    if la and la == lb:
        s += 0.30; ev.append("label identical")
    elif la and lb:
        r = difflib.SequenceMatcher(None, la, lb).ratio()
        if r > 0.85:
            s += 0.22; ev.append(f"label similar ({r:.2f})")
        elif r > 0.7:
            s += 0.10; ev.append(f"label close ({r:.2f})")

    da, db = set(words(a["definition"])), set(words(b["definition"]))
    if da and db:
        j = len(da & db) / len(da | db)
        if j > 0.6:
            s += 0.25; ev.append(f"definitions overlap strongly ({j:.2f})")
        elif j > 0.35:
            s += 0.14; ev.append(f"definitions overlap ({j:.2f})")
        elif j > 0.18:
            s += 0.06; ev.append(f"definitions overlap weakly ({j:.2f})")

    # A WCO class often corresponds to a vocab.unece.org property: WCO models Consignor as a class,
    # the vocabulary models consignor as a relation. That is a real correspondence and the most
    # useful kind to record, so it is noted and related rather than discarded.
    if a["kind"] != b["kind"]:
        # A code list only ever corresponds to a code list. The class-against-property case is a
        # real correspondence - WCO models Consignor as a class, the vocabulary as a relation - but
        # a code list matched against a property is noise.
        if "code-list" in (a["kind"], b["kind"]):
            return 0.0, "different kinds of term"
        s -= 0.08; ev.append("class against property, so related rather than equivalent")

    if a["kind"] == b["kind"] == "code-list":
        ka, kb = list_key(a["local"]), list_key(b["local"])
        if ka and ka == kb:
            s += 0.55; ev.append("same list name once code and list are removed")
        elif ka and kb and ka.rstrip("s") == kb.rstrip("s"):
            s += 0.45; ev.append("same list name but for plural")
        # An alias is the name of a property that ranges at this list, used where the list itself
        # is named after an external reference rather than after the concept. Weaker evidence than
        # the list's own name, because several properties may range at one list.
        for alias in a.get("aliases") or []:
            if list_key(alias) and list_key(alias) == kb:
                s += 0.35
                ev.append(f"a property ranging at this list is named {alias}")
                break
    return min(s, 1.0), "; ".join(ev)


def main():
    if not UNECE_ONT.exists():
        print(f"vocab.unece.org ontology not found at {UNECE_ONT}; set UNECE_ONTOLOGY", file=sys.stderr)
        return 2

    wco = rdflib.Graph()
    for f in sorted(ONT.glob("*.ttl")):
        if f.name != "mappings.ttl":
            wco.parse(f, format="turtle")
    unece = rdflib.Graph()
    for f in sorted(UNECE_ONT.rglob("*.ttl")):
        try:
            unece.parse(f, format="turtle")
        except Exception:
            continue

    wco_terms = name_externals(load_terms(wco, "https://vocabulary.wcoomd.org/"), wco)
    unece_terms = [t for t in load_terms(unece) if "/vocabulary/" in t["iri"] and "/module/" not in t["iri"]]
    print(f"{len(wco_terms)} WCO terms against {len(unece_terms)} vocab.unece.org terms")

    # Index by first word so the comparison is not 283 x 1000 on every signal.
    index = defaultdict(list)
    for t in unece_terms:
        for w in set(tokens(t)) | {t["local"].lower()}:
            index[w].append(t)

    # Only a human decision is carried forward. The script's own earlier guess must not be
    # preserved as though a reviewer had made it, or the thresholds could never be changed.
    existing = {}
    if LEDGER.exists():
        for row in csv.DictReader(LEDGER.open()):
            if (row.get("decided_by") or "auto") != "auto":
                existing[(row["wco_term"], row["unece_term"])] = row.get("decision", "")

    rows = []
    for a in wco_terms:
        seen, best = set(), []
        for w in set(tokens(a)) | {a["local"].lower()}:
            for b in index.get(w, []):
                if b["iri"] in seen:
                    continue
                seen.add(b["iri"])
                sc, ev = score(a, b)
                if sc >= REVIEW:
                    best.append((sc, ev, b))
        for sc, ev, b in sorted(best, reverse=True, key=lambda x: x[0])[:3]:
            published = b["iri"].replace("https://test.uncefact.org/vocabulary/", UNECE_PUBLISHED)
            key = (a["iri"], published)
            rows.append({
                "wco_term": a["iri"], "wco_kind": a["kind"], "wco_label": a["label"],
                "unece_term": published, "unece_label": b["label"],
                "score": f"{sc:.2f}",
                "relation": ("skos:relatedMatch" if a["kind"] != b["kind"]
                             else "skos:exactMatch" if sc >= 0.97 else "skos:closeMatch"),
                # A decision already recorded by a reviewer always wins.
                "decision": existing.get(key) or ("accepted" if sc >= ACCEPT else "review"),
                "decided_by": "human" if key in existing else "auto",
                "evidence": ev,
                "wco_definition": (a["definition"] or "")[:300],
                "unece_definition": (b["definition"] or "")[:300],
            })

    MAP.mkdir(exist_ok=True)
    rows.sort(key=lambda r: (-float(r["score"]), r["wco_term"]))
    with LEDGER.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["wco_term"])
        w.writeheader()
        w.writerows(rows)

    accepted = [r for r in rows if r["decision"] == "accepted"]
    lines = [
        "# WCO Data Model vocabulary — mappings to vocab.unece.org",
        "# Generated by scripts/map_to_unece.py from mappings/wco-to-unece.csv. Do not edit by hand:",
        "# edit the decision column in the CSV and run the script again.",
        "",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
    ]
    for r in accepted:
        lines.append(f'<{r["wco_term"]}> {r["relation"]} <{r["unece_term"]}> .')
    (ONT / "mappings.ttl").write_text("\n".join(lines) + "\n")

    covered = len({r["wco_term"] for r in accepted})
    print(f"  candidates: {len(rows)} over {len({r['wco_term'] for r in rows})} WCO terms")
    print(f"  accepted automatically: {len(accepted)} covering {covered} terms ({covered/len(wco_terms):.0%})")
    print(f"  awaiting review: {sum(1 for r in rows if r['decision'] == 'review')}")
    for kind in ("class", "property", "code-list"):
        n = len({r["wco_term"] for r in rows if r["wco_kind"] == kind})
        total = sum(1 for t in wco_terms if t["kind"] == kind)
        print(f"  {kind}: {n} of {total} with a candidate")
    print(f"  ledger: {LEDGER.relative_to(ROOT)}   mappings: ontology/mappings.ttl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
