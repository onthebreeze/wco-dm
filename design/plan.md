# Plan: publishing the WCO Data Model as linked data

Derived from `hld.dm`. Records the decisions taken on 17 October 2026 and the order of work.

## Decisions

| Question | Decision |
|---|---|
| Licensing | Publish in full, including WCO definitions. The licensing judgement is the repository owner's; it is recorded in the README and on the governance page. |
| Namespace | Source carries `https://vocabulary.wcoomd.org/`, a WCO-owned base. The build overrides it for any other host, exactly as vocab-bsp does with `VOCAB_BASE`, so nothing needs re-homing when WCO takes it over. |
| Document schemas | Deferred. Neither spreadsheet carries cardinality, so a schema generated from them could not say what a message requires. Stage D waits for the information package exports. |
| Deployment | Prepared, not performed. The infrastructure definition, pipeline and DNS script are written so that bringing up `test-wcodm.trade-commons.org` is one command once the account exists. |

## What the source actually contains

Measured, not assumed, from the two workbooks in `raw-data/`.

| | |
|---|---|
| Classes | 273 distinct |
| Attributes | 1,156 |
| Library rows | 1,429 |
| Core data types | 37 (Data Set 1.5) |
| Code lists | 135 (Data Set 1.6), of which 12 carry their values and 123 reference an external list |
| OIS rows | 9,803: 1,993 class occurrences and 7,810 element occurrences |
| Information packages | DEC 9,066, LPCO 872, AIP IG 325, AIP RES 275, MDIP 67 |
| Cardinality | absent from both files |

## Two findings that shaped the build

**The superclass flags partition the library.** Every row carries exactly one of NONE, DOC, GOV, LOC,
PAR or TRA, which gives a natural module split: core 695, party 409, document 120, location 101,
government 50, transport 45.

**Tag names are not unique, so they cannot carry IRIs.** `id` appears 174 times as a JSON tag name
and `typeCode` 49 times, because the WCO Data Model names properties within the context of their
class. The dictionary entry name is 1,424 distinct out of 1,428, so IRIs derive from it, in camel
case, with the four genuine duplicates qualified by class ID. The XML and JSON tag names are kept as
annotations so an implementer can map in either direction.

This is the weakness `hld.dm` anticipated. Transliteration comes first because it is mechanical and
lossless; `mappings/normalisation-candidates.csv` then quantifies how far the model could be
normalised, as input to that decision rather than a pre-emption of it.

## Stages

| Stage | Output | State |
|---|---|---|
| A. Extraction | `intermediate/` — one record per class, attribute, data type, code list and OIS occurrence, each carrying its source file, sheet and row, plus a fidelity check that fails if anything is dropped | |
| B. Vocabulary | `ontology/*.ttl` — modules, classes, properties, code lists, lifecycle status, and a validator | |
| C. Mapping | `mappings/wco-to-unece.csv` — scored candidate matches to vocab.unece.org concepts, with evidence, for review | |
| D. Document schemas | JSON Schema and JSON-LD context per information package | deferred, needs cardinality |
| E. Site | `dist/` with a directory per term holding `index.html`, `index.ttl` and `index.jsonld`, plus overview, architecture, governance and maintenance pages | |
| F. Deployment | infrastructure definition, pipeline, DNS script | prepared, not run |

## Traceability

Every generated term carries the source file, sheet and row it came from, so any published statement
can be traced back to a cell in a WCO workbook. The fidelity check is what keeps that honest: it
compares counts at every step and fails the build on a mismatch.
