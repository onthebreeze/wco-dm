# WCO Data Model as linked data

The World Customs Organization (WCO) Data Model version 4.3.0, published as a navigable, resolvable,
content-negotiable linked data vocabulary. Every class, property and code has an address that
answers a reader with a page and a machine with Turtle, JSON-LD or RDF/XML.

## Layout

| | |
|---|---|
| `raw-data/` | The WCO workbooks, as published and unmodified |
| `intermediate/` | Normalised records, each carrying the file, sheet and row it came from |
| `ontology/` | The generated vocabulary: eight TTL modules, 9,449 triples |
| `mappings/` | The ledger of candidate mappings to vocab.unece.org |
| `docs/` | The narrative pages, in Markdown |
| `dist/` | The built site: a directory per term, each with `index.html`, `index.ttl`, `index.jsonld` |
| `scripts/` | The generator and its gates |
| `deploy/` | Infrastructure and pipeline, written but not yet run |
| `design/` | The design note and the plan |

Nothing in `ontology/` or `dist/` is edited by hand.

## Build

```bash
pip install openpyxl rdflib markdown
scripts/build_all.sh
```

Or with the host the site will be served from:

```bash
WCO_BASE=https://test-wcodm.trade-commons.org/ scripts/build_all.sh
```

The identifiers in the source never change; the base is rewritten at build time, so moving the site
does not re-home a term.

## What it produces

| | |
|---|---|
| Classes | 283, including the ten core data types |
| Properties | 409, from 1,156 attributes |
| Code lists | 136, twelve with values and 123 naming an external list |
| Pages | 906, indexed for local search |

## Why 1,156 attributes become 409 properties

The WCO Data Model names a property inside the context of its class, so `id` appears 174 times and
`typeCode` 49. A linked data vocabulary needs one IRI per concept, so attributes sharing a name and
a core data type become one property with many `schema:domainIncludes`, which is how vocab.unece.org
models the same ground. WCO writes a class-specific gloss for each use, and every one is kept as a
scope note naming its class, so nothing is lost.

## What is not here

Document schemas. Neither published workbook states whether an element is mandatory, optional or
repeatable, so a schema generated from them could not say what a message requires. That waits for
the information package exports.

## Licensing

The WCO Data Model is licensed material and is not freely redistributable. This repository is
private for that reason. Check the applicable licence before publishing anything derived from these
files, or before changing the repository's visibility.
