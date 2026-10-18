/**
 * The one site this account serves, and the facts the stacks need about it.
 *
 * The eight UN/CEFACT standards sites run from a sibling application in the UN working repository
 * and share an account, a certificate and a GitLab trust anchor. This one is deliberately separate:
 * the material is WCO's, the repository is on GitHub, and keeping the account to itself is what
 * makes handing it to WCO a transfer rather than a migration.
 */
export const DOMAIN = 'trade-commons.org';

/** The hostname this deployment serves. The `test-` prefix is what says it is not authoritative. */
export const HOSTNAME = `test-wcodm.${DOMAIN}`;

/** Where the production site is intended to live. Recorded, not used. */
export const PRODUCTION = 'vocabulary.wcoomd.org';

/** The bucket. One per account here, so the name needs no site suffix. */
export const BUCKET = 'wco-test-vocabulary';

/**
 * The machine representations the generator emits beside each index.html. A format left out of
 * this list falls through to HTML rather than rewriting to a key that is not there, so it must
 * match what scripts/build_site.py writes.
 */
export const FORMATS = ['ttl', 'jsonld', 'rdf'];

/**
 * Keep this deployment out of search results. It is an unofficial rendering of licensed material
 * and must not compete with WCO's own publication. The pages carry a banner saying so; this stops
 * the crawl in the first place.
 *
 * A production deployment at vocabulary.wcoomd.org would set this false, which is why the stack
 * takes it as a value rather than assuming one.
 */
export const EXCLUDE_FROM_SEARCH = true;

/** GitHub's OpenID Connect issuer, the trust anchor for the deploy role. */
export const GITHUB_ISSUER = 'https://token.actions.githubusercontent.com';

/** The repository and branch allowed to assume that role. Nothing else can. */
export const REPOSITORY = 'onthebreeze/wco-dm';
export const BRANCH = 'main';
