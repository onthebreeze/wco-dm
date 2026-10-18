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

/**
 * The repository and branch allowed to assume the deploy role. Nothing else can: the subject claim
 * pins both, so a workflow in another repository, or on another branch of this one, is refused.
 *
 * `test` rather than `main`, which is the same arrangement the UN/CEFACT standards sites use. Work
 * lands on main continuously; a merge to test is the deliberate act that publishes it. Protect the
 * branch, because push access to it is write access to the bucket.
 *
 * The subject is written with identifiers rather than names because this repository has GitHub's
 * immutable subject claims enabled, so the token carries
 * `repo:<owner>@<owner id>/<repo>@<repo id>:ref:...`. That is the stronger form and worth keeping:
 * a repository renamed, or deleted and recreated under the same name, gets new identifiers and no
 * longer satisfies the condition. The name-based form, which is what most documentation shows,
 * simply never matches here, and the failure reads as a plain authorisation error with nothing to
 * say why.
 *
 *     gh api repos/<owner>/<repo>/actions/oidc/customization/sub
 */
export const REPOSITORY = 'onthebreeze/wco-dm';
export const OWNER_ID = 13426392;
export const REPOSITORY_ID = 1422865470;
export const BRANCH = 'test';
export const SUBJECT =
  `repo:onthebreeze@${OWNER_ID}/wco-dm@${REPOSITORY_ID}:ref:refs/heads/${BRANCH}`;
