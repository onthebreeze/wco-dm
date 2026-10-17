# Deployment

Nothing here has been run. It is written so that bringing the site up is one command once the
account exists.

## What the site needs

A bucket, a CloudFront distribution, and a viewer-request function that appends `/index.html`,
`/index.ttl` or `/index.jsonld` according to the `Accept` header. That is the whole architecture:
the origin is private, the function is a few lines, and nothing runs at request time.

The UN/CEFACT standards sites already run exactly this. The infrastructure definition is at
`governance/technical-architecture/aws-test/cdk/` in the UN working repository, and `sites.ts` is a
table of sites: adding this one is an entry in that table, or the same construct deployed into a WCO
account.

```ts
{
  key: 'wcodm',
  project: 'wco-dm',
  hostname: 'test-wcodm.trade-commons.org',
  production: 'vocabulary.wcoomd.org',
  negotiated: true,     // the point of the site: one IRI, three representations
  deployed: false,
}
```

`negotiated: true` is what switches the edge function from documentation routing to content
negotiation. The vocabulary tree and the narrative pages share one prefix, which the function
handles without a reserved-prefix list because every page is a directory holding its own
`index.*` files.

## The account

The design note asks for a separate `wco-test` account, created under a personal AWS root today and
transferable to WCO later. That keeps the WCO material out of the UN/CEFACT account and makes the
handover a transfer rather than a migration.

Until that account exists, the alternative is to add the site to the existing `unece-test` account
and move it afterwards. Either way the published identifiers do not change, because the namespace is
a build input rather than a property of the host.

## The pipeline

`deploy/gitlab-ci.yml` and `deploy/github-actions.yml` are the same job for either forge: build,
assume a deploy role through OpenID Connect, upload what changed, invalidate. No access key is
stored anywhere; the role trusts the forge's own token for one repository and one branch.

`deploy/aws/upload-s3.py` compares size and digest before writing, so a rebuild uploads only what
changed. It is the uploader the UN sites use, unmodified.

## Order of operations

1. Create the account and grant a principal in it.
2. Deploy the infrastructure, which issues the certificate and creates the distribution.
3. Add the DNS record for the test hostname.
4. Merge to the deployment branch; the pipeline builds and uploads.
5. Verify negotiation before announcing the address:

```bash
curl -sI https://test-wcodm.trade-commons.org/Consignment
curl -s -H "Accept: text/turtle"         https://test-wcodm.trade-commons.org/Consignment | head -5
curl -s -H "Accept: application/ld+json" https://test-wcodm.trade-commons.org/Consignment | head -5
```

A test deployment is excluded from search engines at the edge, so nothing here competes with WCO's
own publications.
