#!/usr/bin/env python3
"""Gates the generated vocabulary must pass. Exits non-zero on any failure, so the build stops
rather than publishing something incoherent.

    python3 scripts/validate_vocab.py
"""
import json
import pathlib
import sys
from collections import Counter

import rdflib
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONT = ROOT / "ontology"
INT = ROOT / "intermediate"
BASE = rdflib.Namespace("https://vocabulary.wcoomd.org/")
SCHEMA = rdflib.Namespace("https://schema.org/")


def main():
    g = rdflib.Graph()
    for f in sorted(ONT.glob("*.ttl")):
        g.parse(f, format="turtle")

    classes = set(g.subjects(RDF.type, OWL.Class))
    props = set(g.subjects(RDF.type, OWL.DatatypeProperty)) | set(g.subjects(RDF.type, OWL.ObjectProperty))
    schemes = set(g.subjects(RDF.type, SKOS.ConceptScheme))
    failures = []

    def gate(name, bad, explain):
        if bad:
            failures.append((name, len(bad), explain, sorted(str(b) for b in bad)[:5]))

    # 1. Every term is labelled, so nothing renders as a bare IRI.
    gate("every term has a label",
         [t for t in classes | props if not list(g.objects(t, RDFS.label))],
         "a term without rdfs:label cannot be displayed")

    # 2. Every term carries a lifecycle state.
    gate("every term has a status",
         [t for t in classes | props if not list(g.objects(t, BASE.termStatus))],
         "governance depends on every term having a state")

    # 3. Every term says which module defines it, which is what the module pages list.
    gate("every term is defined by a module",
         [t for t in classes | props if not list(g.objects(t, RDFS.isDefinedBy))],
         "a term with no module cannot be placed on the site")

    # 4. Every property has at least one domain and one range.
    gate("every property has a domain",
         [p for p in props if not list(g.objects(p, SCHEMA.domainIncludes))],
         "a property with no domain cannot be reached from a class")
    gate("every property has a range",
         [p for p in props if not list(g.objects(p, SCHEMA.rangeIncludes))],
         "a property with no range has no value space")

    # 5. Every domain and range that is a wco: term resolves to a term that exists.
    known = classes | schemes
    dangling = set()
    for p in props:
        for o in list(g.objects(p, SCHEMA.domainIncludes)) + list(g.objects(p, SCHEMA.rangeIncludes)):
            if str(o).startswith(str(BASE)) and o not in known and o not in props:
                dangling.add(o)
    gate("domains and ranges resolve", dangling, "a reference to a term that is not defined would 404")

    # 6. Every term traces back to a source row.
    gate("every term cites its source",
         [t for t in classes | props if not list(g.objects(t, rdflib.URIRef("http://purl.org/dc/terms/source")))],
         "traceability to the WCO workbook is the point of the pipeline")

    # 7. Nothing is defined twice.
    dupes = [t for t, n in Counter(list(g.subjects(RDF.type, OWL.Class))).items() if n > 1]
    gate("no class is declared twice", dupes, "a duplicate declaration means two modules claim it")

    # 8. Every class extracted from the library is in the vocabulary, and nothing else is except
    #    the core data types, which come from Data Set 1.5 rather than the class library.
    report = json.loads((INT / "extraction-report.json").read_text())
    library = {c["class_name"].replace(" ", "") for c in json.loads((INT / "classes.json").read_text())}
    data_type_classes = {str(c).rsplit("/", 1)[-1] for c in classes
                         if (rdflib.URIRef(str(BASE) + "module/data-types"),) and
                         rdflib.URIRef(str(BASE) + "module/data-types") in set(g.objects(c, RDFS.isDefinedBy))}
    from_library = {str(c).rsplit("/", 1)[-1] for c in classes} - data_type_classes
    missing = library - from_library
    unexpected = from_library - library
    gate("every library class is published", sorted(missing),
         f"{len(from_library)} published against {report['counts']['classes']} extracted")
    gate("no class appears that the library does not have", sorted(unexpected),
         "an invented class would not trace back to a source row")

    print(f"{len(classes)} classes, {len(props)} properties, {len(schemes)} concept schemes, {len(g)} triples")
    if not failures:
        print("all gates pass")
        return 0
    print(f"\n{len(failures)} gate(s) failed:")
    for name, n, explain, examples in failures:
        print(f"  {name}: {n} — {explain}")
        for e in examples:
            print(f"      {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
