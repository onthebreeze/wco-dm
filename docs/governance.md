# Governance

Two things are governed here and they are not the same thing. The **WCO Data Model** is owned,
maintained and released by the World Customs Organization. **This publication** is a rendering of a
WCO release as linked data, and it has its own maintainers, its own change process and its own
audit trail. Confusing the two would be the main way this site could mislead, so the division is
stated plainly: WCO decides what the model says; this publication decides only how it is served.

## What is authoritative

The WCO Data Model is the authority. This site is generated from a release of it and is not a second
source of truth. Where this site and the published model differ, the published model is right and
the difference is a defect here.

Four releases are published here - **4.0.0, 4.1.0, 4.2.0 and 4.3.0** - each taken from its Library
and Overall Information Structure workbooks together with its four Information Package workbooks.
Every term records the file, sheet and row it came from, so any statement on this site can be taken
back to the cell that produced it.

Changes to the model itself are a WCO matter. They arrive here as a new release of the workbooks,
and the maintenance process that produces them is WCO's own, documented by WCO. This site does not
restate it and is not a route into it.

## What makes a published data model well-governed

Publishing a data model as linked data moves a burden onto the publisher: once a term has an address
that software resolves, the address has to keep working and keep meaning the same thing. The bar
below is the one this publication holds itself to.

| Requirement | What it means | How this publication meets it |
|---|---|---|
| Owner and namespace | A named owner and a stable namespace | The World Customs Organization, under `vocabulary.wcoomd.org` |
| Human and machine readable | Published as RDF and as pages, not one or the other | Every address negotiates to HTML, Turtle, JSON-LD or RDF/XML |
| Persistent identifiers | A published address resolves indefinitely and never changes meaning | Flat, version-free identifiers; the vocabulary evolves in place |
| Lifecycle, not deletion | A term that falls out of use is marked, not removed | `wco:termStatus`, with retired terms still resolving |
| Versioning where it belongs | Messages are pinned; terms are not | Unversioned vocabulary across four releases, with a schema and context per message per release |
| Change control | A documented, reviewable change process | Generator changes reviewed as a diff in `ontology/` |
| Declared scope | A reader can tell what the model is for and what it excludes | Customs and cross-border regulatory data; see the architecture page |
| Mappings with a status | Relationships to other vocabularies carry their authority | SKOS mappings to vocab.unece.org, each with a recorded decision maker |
| Traceability to source | Every published statement can be traced to its origin | File, sheet and row recorded per term |
| Maintenance contact | A route to report a problem | Issues on the repository that generates the site |

## Term lifecycle

Every class, property, code list and code value carries a `wco:termStatus`, and with it the release
that introduced the term and, where it has gone, the release that dropped it.

| State | Meaning |
|---|---|
| proposed | Put forward, not yet part of the published model |
| active | Part of the published WCO Data Model |
| deprecated | Still published, but its use is discouraged |
| retired | Withdrawn, and retained so that existing references still resolve |

The vocabulary is built from every release at once, so a term introduced in 4.1.0 says so, and one
dropped after 4.1.0 is published as deprecated rather than left out. A term never disappears: it
keeps its address and says what became of it, because an identifier that stops resolving breaks
every document that ever used it.

Identity across releases is the WCO identifier rather than the name. Attribute 429 is Traveller
status code in 4.1.0 and Traveler status code in 4.2.0; by name that is a removal and an addition,
by identifier it is the rename it was, and the earlier name is kept as an alternate label.

## Versioning: the vocabulary evolves, the messages are pinned

A versioned vocabulary forces every consumer to choose a version and forces every reference to be
rewritten when that version moves. This vocabulary carries no version in its identifiers. It evolves
additively: new terms are added, existing identifiers keep their meaning, and a correction is a new
term with the old one deprecated. Every durable web vocabulary works this way.

Versioning lives at the message layer instead. A JSON Schema and a JSON-LD context are released
against a stated WCO Data Model version, so a document validated against the 4.3.0 schemas can be
validated the same way later. The vocabulary moves; the schemas are fixed points on it.

## The authority of a mapping

The SKOS mappings to the UN/CEFACT vocabulary at vocab.unece.org are assertions about equivalence,
and an equivalence that is wrong is worse than one that is missing, because it will be acted on. Each
mapping therefore records who decided it.

Candidates are proposed by a scoring matcher that compares names, definitions and value domains. A
proposal is a proposal: it carries `decided_by` of `script` and is published as a candidate, not as a
mapping. A mapping becomes normative only when a person has accepted it, at which point
`decided_by` becomes `human` and later runs of the matcher leave it alone. Thresholds can therefore
be retuned without losing review work.

Automated proposal is useful for finding candidates and for spotting gaps. It is not the authority
for an equivalence that anyone will rely on.

## Traceability and audit

Three things together make the publication checkable rather than merely plausible.

**Provenance in band.** Every term carries the workbook, sheet and row it was derived from, so a
reader who doubts a definition can go to the source cell.

**An independent read of the source.** A second script re-reads both workbooks without using the
extractor's output and compares counts and names, so a fault in the extractor cannot pass unnoticed
by agreeing with itself.

**A reviewable diff.** The vocabulary is committed as Turtle. A change to a new WCO release, or to
the generator, shows up as a line-by-line diff that can be read before it is published, and eight
validation gates run over the result. The checks and what each one catches are described under
[how it is maintained](/docs/maintenance/).

## Stewardship by module

Classes are grouped into modules, and the module is metadata rather than part of any identifier. A
module can therefore be stewarded by different people, and a term can be re-homed from one module to
another, without a single published address changing.

## Licensing

The WCO Data Model is licensed material and the World Customs Organization sets the terms on which it
may be used. Publishing it in this form is a decision for the publisher of this site, and anyone
reusing what is published here should check the applicable WCO licence rather than assume the
licence of the generator.
