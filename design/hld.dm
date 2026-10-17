Publishing the WCo Data model as a fully navigable, resolvable, content-negotiable linked data set.

* The goal is to end up with the WCO data model published as a test endpiont at test-wcodm.trade-commons.org and including a full linked data vocabulary and document schema.
* The source is this independent github repo that can be transferred to a WCO GitHub org at any time.  The deployment target is a separate wco-test AWS account, initially created under my own steve.capell@gmail.com AWS root account but transferrable to WCO at any time.
* The architecture is similar to Vocab and UNVTD where the underlying vocabulary comprises classes, properties, code-lists maintained as TTL and published as content-negotiable snippets - in a very similar way to vocab.unece.org. 
* The WCO documents / messages are published as schema and context files that link to the repo - in a very similar architecture to UNVTD.  But in this case the documents and vocab are in the same repo and published together to the same browsable end point.  
* THe underlying vocabulary is unversioned but every class/ property / code has a state lifecycle (proposed - active - deprecated etc - similar to vocab.unece.org).  Documents and their schemae and context files are versioned.  
* The site is styled in a modern way but is distinctly identifier as a WCO site with logo and brand / style.  
* There are overview, architecture, and governance pages similar to vocab.  
* There is rich documentation about hwo the site is maintained and generated.
* There MAY be a need to re-architect the underlying data model - if it is found to have similar weaknesses to the UN/CEFACT CCL and BSP. Traceability from source CSV to published vocab and documents is maintained. 
* Wherever appropriate, every class & property has a SKOS mapping to a corresponding vocab.unece.org concept URI.  
