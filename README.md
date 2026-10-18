# WCO Data Model as linked data

The World Customs Organization (WCO) Data Model, published as a navigable, resolvable,
content-negotiable linked data vocabulary. Every class, property, code list and code value has an
address that answers a reader with a page and a machine with Turtle, JSON-LD or RDF/XML.

Four releases are held here, 4.0.0 to 4.3.0. The vocabulary across them is one unversioned set of
terms, each saying which release introduced it and, where it has gone, which release dropped it.
The messages are versioned, because a format has to be pinned before anyone can validate against
it.

## Layout

| | |
|---|---|
| `raw-data/v<release>/` | The WCO workbooks, as published and unmodified |
| `intermediate/v<release>/` | Normalised records, each carrying the file, sheet and row it came from |
| `ontology/` | The generated vocabulary: ten TTL modules, 11,616 triples |
| `schemas/` | A JSON Schema and a JSON-LD context per message per release |
| `views/v<release>/` | `tree.json` per message: the structure the browser reads |
| `diagrams/` | A conceptual diagram per message per release, PlantUML and SVG |
| `mappings/` | The ledger of mappings to the UN/CEFACT vocabulary |
| `docs/` | The narrative pages, in Markdown |
| `assets/` | The structure browser |
| `scripts/` | The generator and its gates |
| `deploy/` | Infrastructure and pipeline, written but not yet run |
| `design/` | The design note, the plan, and observations about the model |
| `dist/` | The built site: a directory per address, gitignored |

Nothing generated is edited by hand. See `CLAUDE.md` for how the pipeline fits together.

## Build

```bash
pip install openpyxl rdflib markdown
scripts/build_all.sh                 # about 45 seconds
python3 scripts/serve.py 8099        # serves dist/ the way the edge will
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
| Classes | 287: 272 from the library, five superclasses, ten core data types |
| Properties | 452, merged from 1,226 attribute positions across the four releases |
| Code lists | 177: 138 the register holds, 38 referenced from an external authority |
| Code values | 73, one page each, for the thirteen lists WCO owns |
| Messages | 36, of which 20 are in 4.3.0 and 16 were discontinued before it |
| Schemas and contexts | 106, one pair per message per release |
| Pages | 1,154, each answering in four representations, with a local search index |

Three attribute positions in a hundred are deprecated rather than current: 72 attribute positions
and three code lists were dropped by a later release and are still published, because an identifier
that stops resolving breaks every document that used it.

## Why 1,226 attribute positions become 452 properties

The WCO Data Model names an attribute inside the context of its class, so `id` appears 174 times
and `typeCode` 49. A linked data vocabulary needs one IRI per concept, so attributes sharing a
local name and a core data type become one property with many `schema:domainIncludes`, which is how
the UN/CEFACT vocabulary models the same ground. WCO writes a class-specific gloss for each use,
and every one is kept as a scope note naming its class, so nothing is lost.

Where that merge produces a property whose classes code against different lists, the attributes did
not mean the same thing and the merge is undone. `WCO_SPLIT` chooses how; the default splits by
value domain.

The Library also states which superclass each class belongs to and which superclass element each
attribute realises - that a Carrier is a Party, and that Agent identifier and Carrier identifier
are both S009, identification. That statement is published as `rdfs:subClassOf` and as an
annotation on each property, but nothing is merged on it, so no term's address depends on it.

## Information packages

Each of the four Information Packages, and each derived package that subsets it, has a page saying
what the message is, a conceptual diagram, a browsable structure, and a schema, context and digest
per release. Nothing in any package is mandatory: every position in all four is `0..1` or
`0..unbounded`, so obligation arrives with the regulation or the national profile that uses the
message, and a derived package is the first narrowing.

## Licensing

The WCO Data Model is licensed material and is not freely redistributable. This repository is
private for that reason. Check the applicable licence before publishing anything derived from these
files, or before changing the repository's visibility.
