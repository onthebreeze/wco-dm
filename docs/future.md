# Future improvements

Publishing the WCO Data Model as linked data makes certain things visible that a spreadsheet does
not. What follows is a set of suggestions for a future version of the model, with the evidence for
each, and then the part that matters more than any of them: how a model rebuilt on a different
architecture would still produce the artefacts that implementers depend on today.

Nothing here has been applied. The vocabulary on this site renders WCO Data Model 4.3.0 as the
workbooks give it, and the counts below can be reproduced from them.

## Roles are modelled as classes, and the role is also carried as data

The Library flags every class with a SuperClass Usage of NONE, DOC, GOV, LOC, PAR or TRA. 171 of
the 273 classes carry one. It is a flag and not a parent: there is no Party class, no Location
class and no Document class in the Library, so there is nothing to inherit from and nothing to
point at. What the flag marks is that a class uses the superclass's standard attributes, which it
then restates under its own name - `Agent identifier`, `Applicant identifier`, `Assembler
identifier`.

Ninety classes are flagged PAR. Taken as named they have 90 distinct attribute signatures. Remove
the class name from the front of each attribute and they collapse to 28, and one signature covers
43 of them:

| | |
|---|---|
| Classes flagged PAR | 90 |
| Distinct signatures, attributes as named | 90 |
| Distinct signatures, class name removed | 28 |
| Classes sharing the commonest signature | 43 |

That signature is identifier, name, identification issuing country code, role code. Ten more carry
it without the name and five add a category of person code, so about 58 of the 90 differ from one
another in nothing but what they are called: Applicant, Assembler, Authenticator, AuthorizedPerson,
Carrier, Consolidator, ConsortiumCarrier, Deconsolidator, Distiller, Stevedore and the rest.

**83 of those 90 classes already carry a Role code attribute.** The role is therefore expressed
twice, once as the class and once as a value inside it, and two statements that can disagree.

The pattern repeats more mildly elsewhere. Fourteen of the 23 classes flagged GOV have exactly one
attribute, an identifier: AppealOffice, BorderingOffice, ContactOffice, ExitOffice, ExportOffice,
GuaranteeOffice, ItineraryOffice, PaymentOffice, PresentationOffice, SupervisingOffice among them.
Six of the 33 flagged LOC are an identifier and a name.

Not all of them are roles. MasterDataOffice carries a country code and a validity period,
EntryOffice carries a sequence number, and the transport classes have substantial structure. The
difficulty is that the model states no rule separating the two cases, so the question has been
answered differently in different places.

### A principle worth stating

A class earns its own identity when it has state or structure the general class does not: an
attribute, a relationship or a lifecycle of its own. A distinction carried entirely by which
property points at it is a role, and a role belongs in the data, or in the property name at the
point of use, rather than in a new class.

The test is mechanical. Strip the class name from the front of each of its attributes. If what
remains is a subset of the general class's attributes, it is a role.

### What the present design buys

The role-as-class pattern is not an accident, and a future version should keep what it provides.
The tag names the position unambiguously without a discriminator, which is what XML and EDIFACT
before it needed. Cardinality can differ per role, one Exporter and many Carriers, without a
conditional rule. A constraint can attach to one role without attaching to parties in general.

All three survive the change, because they are properties of the message rather than of the
dictionary. A message can still have an `exporter` and a `carrier` element, each constrained
differently, both ranging at Party. What is given up is 90 class definitions that say almost
nothing, and what is gained is the ability to state that all of them are parties.

## Attributes are named inside their class

`identifier` occurs 174 times across the Library and `typeCode` 49, each as its own attribute with
its own ID and definition, and the definitions are usually the same sentence with a different class
name in it.

This site merges them, because a vocabulary cannot work otherwise: an attribute sharing a local
name and a core data type becomes one property carrying many domains, and every class-specific
wording is kept as a scope note. The merge is only safe where the value domains agree, and in
twelve cases they did not, which is the useful part. Those twelve are places where one name was
doing two jobs, and a model that named properties once would have had to resolve them.

## Nothing is mandatory

Every position in all four Information Packages is `0..1` or `0..unbounded`. There is not one
minimum of 1 in 9,064 Declaration positions, 763 LPCO, 440 AIP or 67 MDIP.

That is defensible for a catalogue, and obligation does belong to the regulation that uses it. The
consequence is that the model carries no machine-readable statement of what any message actually
requires, which is the first thing an implementer asks for. A profile mechanism - a named set of
constraints over a package, versioned and published like the package itself - would give that
answer without making the catalogue itself stricter. The derived packages are half of this already:
they say which positions a message uses, but not which it demands.

## The code list register names lists in prose

The register gives each list's basis as free text, and the citations that point at it are free text
too. Of the 573 places where an attribute cites a code list, 214 resolve to exactly one entry in the
register. 140 match more than one, because several registered lists share a basis string and the
citation cannot say which is meant. 219 match none at all: some name an external authority's list
the register does not hold, and 36 of those are minted here as referenced schemes so that a coded
property has something to resolve to; 138 are guidance rather than a reference, such as "UN/LOCODE +
User codes OR User code list" or "Proposed guideline: Use relevant laws, treaties OR regulations :
User code list".

A consumer cannot tell from the register alone whether a list has values, where they come from, or
whether two attributes citing the same sentence mean the same list. An identifier in place of a
sentence settles all three, and the identifier can be a resolvable address.

## Identity is positional

A term's identity in the Overall Information Structure is its path and its Unique Position ID. That
makes identity a function of where something sits, so the same concept in two places is two
positions, and moving a branch changes identities that documents may already reference.

Separating the two kinds of identity would help: a term identified by an address that does not
change, and a position identified by its path within a message. The present model has both but
treats the position as primary. This publication inverts that, which is why it can say that 9,059
of the Declaration's 9,064 positions are occurrences of terms defined elsewhere.

## Version 5.0 as an inversion

Everything above is a modelling suggestion. The structural change is simpler to state and larger in
effect: turn the arrow around.

Today the spreadsheets are the model and the linked data is derived from them. This site is that
derivation - workbooks in, vocabulary and schemas and pages out, nothing hand-maintained in
between. The vocabulary is a rendering, which is why this site says that where it and the published
model differ, the published model is right.

Version 5.0 would make the linked data vocabulary and the information models the authoritative
source, and generate the spreadsheets, the XML schemas and the JSON schemas from them.

```
today   workbooks  ->  vocabulary, schemas, contexts, site
5.0     vocabulary + information models  ->  workbooks, XSD, JSON Schema, contexts, site
```

The pipeline does not have to be invented, because it already exists and runs in one direction. The
generators, the validation gates, the fidelity check and the publication are the same machinery
pointed the other way. What changes is which end is edited.

That has consequences beyond tidiness. A change becomes a diff over the model rather than an edit
to a cell, so a Data Maintenance Request can be reviewed as a proposal with its effects visible. A
term gets an address before it gets a position in a message, rather than the other way round. The
spreadsheets stop being a thing to maintain and become a thing to publish, which means they can
continue to be published for as long as anyone needs them.

## Information packages that reference other vocabularies

The inversion opens a second possibility, and it is the one with the most value in it for Members.
Once the model is linked data, a position in an Information Package binds to a term by address, and
that address does not have to be WCO's.

Structure stays WCO's. A Declaration is a WCO artefact: which positions exist, what they are called
on the wire, how many times each may occur, which message carries which. Meaning can be borrowed.
A position for a country code can point at the country code scheme that already exists rather than
at a WCO restatement of it.

The model does this already, in prose. Of the 135 entries in the code list register:

| Cites | Entries |
|---|---|
| UN/EDIFACT code lists | 76 |
| User code list, left to the implementer | 29 |
| WCO's own lists | 17 |
| ISO 3166, ISO 4217, IMO, UN/LOCODE | 6 |
| Other | 7 |

More than half the register names a UN/CEFACT list. UN/CEFACT is publishing those same lists as
resolvable concept schemes at vocab.unece.org, so the difference between the two models is not that
one owns the codes and the other does not. It is that one names them in a sentence and the other
gives them an address.

### What becomes available

**UN/CEFACT, at vocab.unece.org.** The 76 EDIFACT lists, the units of measure from Recommendation
20, and the Buy-Ship-Pay trade terms. The same intergovernmental tier of governance as the WCO Data
Model itself, and the vocabulary this site already carries candidate mappings into: 123 candidates,
14 strong enough to propose as matches, all awaiting a human decision. That register lists the WCO
Data Model as a planned mapping target, so the correspondence is wanted from both ends.

**UN/LOCODE.** Locations, becoming a register with a resolvable address per location. Customs
declarations are full of places.

**schema.org.** Organization, Person, PostalAddress, QuantitativeValue. Not an authority for
customs, but the vocabulary that general-purpose software already understands, which is what makes
a declaration's party and address legible to a system that was never built for customs.

**GS1.** Identifiers for goods, parties and locations that are already on the carton. A declaration
that can say its goods identifier is a GTIN, by address rather than by convention, is a declaration
a supply chain system can join to its own data without a mapping project.

**W3C.** RDF, SKOS and OWL as the substrate. Beyond that, Verifiable Credentials and Decentralized
Identifiers, which is how a certificate of origin or a licence can be checked for authenticity
without calling the issuer, and which the UN Transparency Protocol already builds on.

**ISO.** 3166, 4217, 6346. Already cited by the register, and already published.

### What WCO keeps

Borrowing concentrates effort rather than dispersing it. Nobody else defines a customs procedure
code, the duty, tax and fee structure, the declaration lifecycle, the control and release decision,
or the relationship between a declaration and a consignment. That is where the model's authority
is, and it is a smaller and more defensible surface than 273 classes of which 90 are parties.

### What makes it safe rather than loose

The mechanism matters as much as the idea, and it is the one vocab.unece.org implements.

**A register of recognised vocabularies**, each admitted against stated criteria: a named owner, a
stable namespace, persistent addresses, a documented change process, and a maintenance contact.
Recognised is not the same as open-ended. Without admission criteria a register accumulates
abandoned vocabularies, and a weak scheme ends up looking equivalent to a governed one because both
happen to be machine-readable.

**Every mapping carries its authority.** A correspondence proposed by software is a candidate; one
accepted by a person is a mapping; one agreed with the vocabulary's owner is stronger again. This
site already records that distinction, and all 123 of its candidates are still marked as the
script's work rather than anyone's decision.

**Contexts are pinned.** What a message means depends on the context it references, so a context
that could be altered later would change retrospectively what every past document said. Each
release here already publishes the digest of its schema and its context for that reason, and a
borrowed vocabulary has to be pinned the same way, by version or by digest.

**Jurisdiction can override.** Where a destination's regulation mandates a particular vocabulary,
that is a fact about the shipment, and the model should be able to record which vocabulary governs
rather than assuming one answer everywhere.

### It does not touch the wire

A borrowed term keeps its WCO identity: its Class or Attribute ID, its XML tag, its JSON tag, its
Dictionary Entry Name. The generated 4.x artefacts are therefore unchanged, because the borrowing
happens in the semantic layer, in the JSON-LD context, and not in the message format. An
implementer who never looks at the vocabulary sees the same XSD they see today. One who does look
gets a term that resolves, and resolves into a vocabulary with its own community, tooling and
maintenance behind it.

That is the trade in one line: the same declaration, understood by more systems, maintained by
fewer people.

## Backwards compatibility

Inverting the paradigm is only safe if the artefacts people have built against keep arriving, and
that is exactly what inverting it makes possible: once the model is the source, the 4.x forms are
outputs like any other.

**Generate the 4.x artefacts from the 5.0 model.** The XML schemas, the JSON schemas, the
Information Package workbooks and the Library spreadsheet become build outputs. An implementer who
has built against 4.3.0 continues to receive what they built against, from a release process rather
than from a maintained copy.

**Keep every 4.x identity in the model, not in a side table.** Each 5.0 term carries the Class ID,
Attribute ID, Unique Position ID, XML tag, JSON tag and Dictionary Entry Name it had in 4.x, as
annotations on the term. The mapping is then part of the thing it maps, it is published and
resolvable like everything else, and it cannot drift out of step with the model the way a
spreadsheet of correspondences would.

**A collapse must record what it collapsed.** If Carrier becomes Party with a role code, the model
records that correspondence - the 4.x class name, its class ID, and the role value that reproduces
it - so the generator can expand Party plus role back into the 4.x class and its class-specific
attribute names. This is the point on which the whole approach turns: a change that cannot be
expressed as a reversible rule is a change that breaks compatibility, and knowing which changes
those are is most of the design work.

**Message structure barely moves.** An Information Package is a tree of paths over terms, and
re-homing the terms does not change the tree. The Declaration still has a Consignment at the same
path with the same cardinality, whatever the dictionary beneath it looks like.

**Prove it rather than assert it.** The compatibility claim is testable, and should be tested on
every release: regenerate the 4.3.0 artefacts from the 5.0 model and diff them against the
published 4.3.0 artefacts. A difference is either a defect in the generator or a documented,
accepted change. Then round-trip real instance documents: every 4.x document validates against the
generated 4.x schema, converts to its 5.0 representation and back, and arrives unchanged.

**Be explicit about what cannot survive.** A term introduced in 5.0 has no 4.x form, so it can only
appear in 5.x messages; generation into a 4.x artefact must drop it and say so rather than invent a
tag. A term 5.0 deprecates keeps resolving and keeps its generation rule until the 4.x line is
retired, which is a published date rather than an assumption.

Compatibility built this way is a property of the release process rather than a migration project.
It also sets the terms of the trade honestly: the cost of a cleaner model is a generator and a test
suite that have to be maintained for as long as the old line is supported, and that cost is
visible, bounded and far smaller than asking every implementer to migrate at once.
