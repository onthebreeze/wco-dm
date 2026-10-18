# Deployment

Nothing here has been run. It is written so that bringing the site up is one command once the
account exists.

## What the site needs

A bucket, a CloudFront distribution, and a viewer-request function that appends `/index.html`,
`/index.ttl`, `/index.jsonld` or `/index.rdf` according to the `Accept` header. That is the whole
architecture: the origin is private, the function is a few lines, and nothing runs at request time.

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
  negotiated: true,                        // one address, four representations
  formats: ['ttl', 'jsonld', 'rdf'],       // this generator emits RDF/XML as well
  deployed: false,
}
```

`negotiated: true` is what switches the edge function from documentation routing to content
negotiation. `formats` says which machine representations this generator actually emits: a format
left out of it falls through to HTML rather than rewriting to a key that is not there, which is why
adding RDF/XML is a change in the generator first and in that line second.

The vocabulary tree, the message pages and the narrative pages share one prefix, and the function
handles all three without a reserved-prefix list because every page is a directory holding its own
`index.html`, `index.ttl`, `index.jsonld` and `index.rdf`. The build fails if any page is missing
one, so the invariant the edge depends on is checked where it is created rather than assumed.

One thing the router had to learn for this site: a version is a path segment, not a file
extension. A release is published at `/packages/<package>/<message>/4.3.0/`, and the old rule
treated anything after a dot as a file, which would have sent every release page to a key that does
not exist. An extension now has to begin with a letter.

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
host=https://test-wcodm.trade-commons.org
for path in / /Consignment /module/party /classes/ /docs/architecture \
            /packages/declarations/mar-api/4.3.0; do
  for accept in text/html text/turtle application/ld+json application/rdf+xml; do
    printf '%-44s %-22s %s\n' "$path" "$accept" \
      "$(curl -s -o /dev/null -w '%{http_code} %{content_type}' -H "Accept: $accept" "$host$path")"
  done
done
```

`python3 scripts/serve.py 8099` applies the same rule locally, so the matrix above can be run
against a build before anything is deployed.

A test deployment is excluded from search engines at the edge, so nothing here competes with WCO's
own publications.
