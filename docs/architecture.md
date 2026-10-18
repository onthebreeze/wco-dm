# Architecture

## Meaning, structure and rules

Three things are easily confused and are kept apart here, because each changes at a different rate
and is owned by different people.

**Meaning** is what a term is. `Consignment` is a collection of goods moved from one consignor to
one consignee under one transport contract, and that is true whether it appears in an export
declaration, a certificate of origin or a postal item. The WCO Data Model Library is the dictionary:
273 classes and 1,156 attributes, each with a definition and an identifier, saying nothing about the
shape of any message.

**Structure** is how terms are assembled into a message. A Declaration arranges them one way, a
Licence another, and both draw on the same dictionary. Structure says what may appear, in what
order, and how many times. The Information Packages own this.

**Rules** are what a particular exchange requires. A Certificate of Origin under the WCO Technical
Committee on Rules of Origin uses part of the LPCO package; eTIR uses part of the Additional
package. The same structure, constrained for a context. Derived Information Packages own this.

Keeping them apart is what lets the dictionary stay small and stable while messages multiply. A term
is defined once and reused; a message borrows meaning rather than redefining it; a derived package
narrows a message without forking either.

## How the WCO Data Model is layered

The model arrives as a set of workbooks that correspond to those layers.

| Layer | What it holds |
|---|---|
| Library | What each class and attribute means, and its identifier |
| Overall Information Structure | Every information model consolidated into one tree, each node with a path and a Unique Position ID |
| Content Information Structure | The same tree with the technical metadata removed, so what remains is business content |
| Information Packages | The subsets that correspond to a kind of exchange |
| Derived Information Packages | A package cut down to what one real message uses |

The Information Packages are four. The two Base packages carry business information: **Declaration**
for business to government submissions, and **LPCO** for licences, permits, certificates and other
documents. The **Additional** package wraps business information for a different audience, as a
Response to business or an Intergov exchange between administrations. The **Meta Data** package
carries the technical aspect of the exchange and is deliberately separate, so the others hold only
content.

## Composition, not association

The relationship between an Additional package and a Base package is composition rather than
association. They are separate information models: the parent holds an empty class as a placeholder
for the root of the child. That matters at implementation, because it can be realised either way.

**Merged**, where the two schemas become one and the Additional package is the root. **Detached**,
where they stay separate, either as siblings in one schema or in different payloads entirely. The
same relationship holds between the Meta Data package and anything it wraps.

The model does not choose for you, and neither does this publication: the schemas here follow the
package structure as the workbooks give it.

## What this publication adds

The model is published as spreadsheets. Here the same content is published so that software can
follow it.

**Every term has an address.** `https://vocabulary.wcoomd.org/Consignment` is the class, not a row
in a sheet. A system meeting an unfamiliar identifier can resolve it and find out what it means.

**One address, three representations.** The same URI answers a reader with a page and a machine with
Turtle or JSON-LD, selected by the `Accept` header. Nothing is duplicated to achieve it.

**Messages carry their cardinality.** A JSON Schema per Information Package, and per derived
package, generated from the Number of Occurrences the workbooks record. That is what lets a schema
say an element is required or repeatable rather than merely present in the model.

**Terms are mapped outward.** Where a concept corresponds to one in the UN/CEFACT vocabulary at
vocab.unece.org, the term carries a SKOS mapping, so a reader crossing between the two can see where
they meet.

## Naming

**Flat term IRIs.** A class or property is `https://vocabulary.wcoomd.org/<Term>`. No module and no
version in the path: the module is metadata, so a term can move between modules without its
identifier changing.

**Path-style code IRIs.** A code list is `/code-list/<list>` and a value is `/code-list/<list>/<code>`,
so a value is identified within the list that gives it meaning.

**Lists are named apart from properties.** The WCO register names a list after the attribute it
serves, which makes `TypeCode` both a property and a list. Every registered list therefore carries a
`List` suffix: the property is `typeCode`, the list is `TypeCodeList`, and the register's own name is
kept as an alternate label.

**Identifiers are stable.** A published IRI does not change meaning. The namespace is a build input
rather than a property of the source, so the same identifiers are served from a test host and from
the production one.

## Three kinds of term

A code list is a term in its own right, not a detail of the property that uses it. The vocabulary
has three categories and each has its own index, its own addresses and its own pages.

**Classes** are groups of information the model treats as things. Each carries its WCO class
identifier.

**Properties** are single pieces of information about a class. The WCO Data Model names a property
inside the context of its class, so `id` occurs 174 times across the library and `typeCode` 49. Here
a property is one term used by many classes, with every class-specific definition kept as a scope
note, which is how the UN/CEFACT vocabulary models the same ground. Where the classes using a name
code against different lists they did not mean the same thing, and the property is split by value
domain so that every property can say what its values are.

**Code lists** are the value domains. Each is a SKOS concept scheme, and the scheme is the datatype:
a coded property ranges at the list rather than at a string. Where WCO owns the codes they are
published here with an address each; where the list belongs to another authority the scheme records
what it is based on and leaves the values to them.

## Versions

The vocabulary is unversioned and its terms carry a lifecycle instead; message schemas are versioned,
because a message format has to be pinned. Terms are stable and long-lived, messages are released.
The policy, and the term lifecycle it rests on, are set out under [governance](/docs/governance/).
