# Plan: publishing the WCO Data Model as linked data

Derived from `hld.dm`. Records the decisions taken on 17 October 2026 and the order of work.

## Decisions

| Question | Decision |
|---|---|
| Licensing | Publish in full, including WCO definitions. The licensing judgement is the repository owner's; it is recorded in the README and on the governance page. |
| Namespace | Source carries `https://vocabulary.wcoomd.org/`, a WCO-owned base. The build overrides it for any other host, exactly as vocab-bsp does with `VOCAB_BASE`, so nothing needs re-homing when WCO takes it over. |
| Document schemas | Done, once the Information Package workbooks arrived on 18 October. They carry Min and Max per node, which the library does not, so a schema can state what a message requires. |
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
| Cardinality | absent from the library and the OIS; carried per node by the four Information Package workbooks |

## The Information Packages

Added 18 October. The library says what a class and an attribute mean; these say how they assemble
into a message.

| Package | Nodes | Depth | Repeating | Derived packages |
|---|---|---|---|---|
| Declaration | 9,064 | 11 | 1,842 | Maritime API, Maritime BRI, UPU CUSITM, UPU REFRSP |
| LPCO | 763 | 8 | 171 | Certificate of Origin (WCO TCRO), Customs Bond |
| Additional | 440 | 6 | 92 | eTIR, SSTL, AEO Master Data, AEOMRA, CNTRL, INF, BUSSVAL, TECHVAL, STA, UPU CUSRES |
| Meta Data | 67 | 5 | 9 | none |

The four workbooks do not share a layout - MDIP has no Remark column, so its Min and Max sit one
place left of everyone else's - so columns are resolved by heading. The derived packages are
identified from the group heading row rather than by looking for columns full of marks, which is
what keeps the Declaration's four from becoming forty by sweeping in the IMO Compendium mapping.

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

## Site framework

Nextra, a Next.js static export, for the narrative pages only. The term pages are generated as plain
files and the two trees merge into one prefix at deploy.

The site is about ten narrative pages and roughly 1,560 generated term pages, each of which needs an
`index.ttl` and an `index.jsonld` beside its `index.html` for content negotiation. No framework
emits that, and rendering 1,560 React routes to obtain it would be slow for nothing. vocab.unece.org
resolves this the same way, and the S3 uploader already merges several source trees into one prefix
with collision resolution, because it was written for that case.

Docusaurus was considered and rejected: it carries versioning machinery this vocabulary does not
want, since the vocabulary is unversioned by design, and it owns routing in a way that complicates
serving a generated tree at the same host. Astro would work but has no sibling precedent for a
vocabulary site and less to reuse.

## Stages

| Stage | Output | State |
|---|---|---|
| A. Extraction | `intermediate/` — one record per class, attribute, data type, code list and OIS occurrence, each carrying its source file, sheet and row, plus a fidelity check that fails if anything is dropped | |
| B. Vocabulary | `ontology/*.ttl` — modules, classes, properties, code lists, lifecycle status, and a validator | |
| C. Mapping | `mappings/wco-to-unece.csv` — scored candidate matches to vocab.unece.org concepts, with evidence, for review | |
| D. Document schemas | JSON Schema and JSON-LD context for each of the four Information Packages and the sixteen derived packages that subset them | done; the package workbooks carry the cardinality the library does not |
| E. Site | `dist/` with a directory per term holding `index.html`, `index.ttl` and `index.jsonld`, plus overview, architecture, governance and maintenance pages | |
| F. Deployment | infrastructure definition, pipeline, DNS script | prepared, not run |

## Traceability

Every generated term carries the source file, sheet and row it came from, so any published statement
can be traced back to a cell in a WCO workbook. The fidelity check is what keeps that honest: it
compares counts at every step and fails the build on a mismatch.
