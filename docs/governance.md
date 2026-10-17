# Governance

## The vocabulary is unversioned; the terms have a lifecycle

A versioned vocabulary forces every consumer to choose a version and forces every identifier to
carry one. This vocabulary has no version in its identifiers. Instead each term carries a state, and
the state is what changes.

| State | Meaning |
|---|---|
| proposed | Put forward, not yet part of the published model |
| active | Part of the published WCO Data Model |
| deprecated | Still published, but its use is discouraged |
| retired | Withdrawn, and retained so that existing references still resolve |

Everything generated from WCO Data Model 4.3.0 is active. A term never disappears: a retired term
keeps its address and says that it is retired, because an identifier that stops resolving breaks
every document that ever used it.

Document schemas are versioned, because a message format has to be pinned. That distinction is
deliberate: terms are stable and long-lived, messages are released.

## What is authoritative

The WCO Data Model is owned and published by the World Customs Organization. This site is generated
from it and is not a second source of truth. Where this site and the published model differ, the
published model is right and the difference is a defect here.

## Licensing

The WCO Data Model is licensed material. The decision to publish it in this form rests with the
publisher of this site, not with the generator. Anyone reusing it should check the applicable WCO
licence.

## Changes to the model, and changes to this publication

A change to the Data Model is a WCO matter and arrives as a new release of the workbooks. A change
to how the model is published here is a change to the generator, and shows up as a diff in
`ontology/` that can be read before it goes out.

The two are deliberately separable. Regenerating from a new WCO release should change the vocabulary
only where WCO changed the model.
