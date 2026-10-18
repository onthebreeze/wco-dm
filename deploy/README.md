# Deployment

The site runs on AWS: a private S3 bucket, a CloudFront distribution in front of it, and one
viewer-request function that chooses a representation by `Accept`. Nothing else runs at request
time. GitHub Actions builds on a push to `test`, assumes a role through OpenID Connect, uploads what
changed and invalidates the distribution. No access key exists anywhere in this pipeline.

Work lands on `main` continuously; merging `main` into `test` is the deliberate act that publishes
it, which is the arrangement the UN/CEFACT standards sites use. The role trusts that one branch of
this one repository and nothing else, so push access to `test` is write access to the bucket.

Deployed. The record of what exists:

| Thing | Value |
|---|---|
| Account | `wco-test`, `335048986725`, in `ou-1o1i-x8n7vhbe` under the standards-test guardrail |
| Budget | `wco-test-monthly`, 20 USD, in the management account where charges consolidate |
| Access | The existing Identity Center user with `AdministratorAccess`; CLI profile `wco-test` |
| Certificate | `arn:aws:acm:us-east-1:335048986725:certificate/5fac64ed-483d-42d5-9bc4-64235735e9bb` |
| Bucket | `wco-test-vocabulary` |
| Distribution | `ENAHS02EQNK12`, `d132ub2gavkkcu.cloudfront.net` |
| Deploy role | `arn:aws:iam::335048986725:role/github-deploy-wcodm` |
| DNS | A and AAAA alias records for `test-wcodm.trade-commons.org` in `Z0512956MDZ08WHZBJGA` |

None of those is a credential.

## What was decided, and why

**Its own account.** `wco-test`, a new account in the same organisation as the UN/CEFACT standards
test sites but not the same account as them. The material is WCO's and licensed, and keeping it
separate makes handing the deployment to WCO a transfer rather than a migration. The cost is a
certificate, a bootstrap and an access assignment that the shared account already had.

**`test-wcodm.trade-commons.org`.** The prefix is what says the site is not authoritative, and it
matches the eight sibling sites.

**Public, not indexed.** The distribution is open to anyone with the address. `X-Robots-Tag:
noindex, nofollow` is set on every response and `/robots.txt` is answered from the edge with a
disallow, both so that this rendering cannot compete with WCO's own publication in search results.
Every page carries a banner saying it is unofficial, generated from WCO's published workbooks, and
that the model is licensed material. The banner is derived from the host rather than from a flag:
any build at a host other than `vocabulary.wcoomd.org` shows it, so a deployment cannot quietly
lose the notice.

That is not access control. If the licence turns out to require it, the next step is a shared
secret checked in the viewer-request function, which is a small change to one file.

## The shape

```
GitHub Actions ──OIDC──> role github-deploy-wcodm ──> bucket wco-test-vocabulary
                                                          │
                              CloudFront distribution ────┘
                                   │         │
                            router.js   headers.js        (viewer request, viewer response)
```

`deploy/cdk/` is the infrastructure. Two stacks: the certificate in `us-east-1`, because CloudFront
accepts no other region, and everything else in `ap-southeast-2`.

The two edge functions are the same files the UN/CEFACT standards sites run, copied rather than
shared because the two deployments are in different accounts and different repositories. The
routing rule is one rule: collapse a trailing slash, pass through anything whose last segment ends
in a file extension, otherwise append `/index.<ext>` chosen by `Accept`. `scripts/serve.py` applies
the same rule locally, so the matrix can be checked before anything is deployed.

Three things in that rule earn their place:

**A file extension must begin with a letter.** A release is published at
`/packages/<package>/<message>/4.3.0/`, which ends in a dot and a digit. CloudFront does not
redirect a directory to its trailing slash the way a local static server does, so treating that as
a file is a 404 in production and a working page in every local test.

**`FORMATS` must match what the generator emits.** This site emits Turtle, JSON-LD and RDF/XML. A
format left out of the list falls through to HTML rather than rewriting to a key that is not there.

**Every page directory holds `index.html`, `index.ttl`, `index.jsonld` and `index.rdf`.** The build
fails if one is missing, which is what lets the function be one rule with no list of exceptions.

## Standing it up

The order matters: infrastructure, then DNS, then content.

### 1. The account

Create `wco-test` in the organisation, in the `standards-test` organisational unit
(`ou-1o1i-x8n7vhbe`), so it inherits the service control policy and the budget pattern the sibling
account uses. Give it a monthly budget of its own.

Then an Identity Center assignment: the existing user with `AdministratorAccess` on the new
account, and a CLI profile named `wco-test` from `aws configure sso`.

### 2. Bootstrap and the certificate

```bash
cd deploy/cdk && npm install
export CDK_DEPLOY_ACCOUNT=<the new account id>
npx cdk bootstrap aws://$CDK_DEPLOY_ACCOUNT/ap-southeast-2 aws://$CDK_DEPLOY_ACCOUNT/us-east-1 \
  --profile wco-test

npx cdk deploy WcoTestCertificate --profile wco-test
```

That stack sits in `CREATE_IN_PROGRESS` waiting for a DNS record it cannot write itself: the hosted
zone for `trade-commons.org` is in the management account. In another terminal:

```bash
cd deploy/cdk/dns && ./validate-certificate.sh
```

The management profile is not an SSO profile. Sign in to the console as the management account's
root user first, then run `aws login`; starting with the command leaves a pending authorisation
that expires in a couple of minutes.

### 3. The site

```bash
npx cdk deploy WcoTestSite --profile wco-test
cd dns && ./upsert-site-record.sh
```

The stack outputs the bucket, the distribution id and the deploy role. Put the account id and the
distribution id into `.github/workflows/deploy.yml`, which is disabled until they are real.

### 4. The content

Merge `main` into `test`, or run the workflow by hand. The workflow refuses to upload a build made
at the wrong host, and refuses one that has lost the unofficial-rendering banner.

## Verifying

```bash
host=https://test-wcodm.trade-commons.org
for path in / /Consignment /module/party /classes/ /docs/artefact-generation \
            /packages/declarations/mar-api/4.3.0; do
  for accept in text/html text/turtle application/ld+json application/rdf+xml; do
    printf '%-46s %-22s %s\n' "$path" "$accept" \
      "$(curl -s -o /dev/null -w '%{http_code} %{content_type}' -H "Accept: $accept" "$host$path")"
  done
done

curl -s "$host/robots.txt"                       # disallow, served from the edge
curl -sI "$host/Consignment" | grep -i robots    # noindex, nofollow
curl -sI "$host/packages/meta-data/4.3.0/MDIP_4p3p0.xsd" | grep -i content-type   # application/xml
```

The same matrix runs locally against `scripts/serve.py`, so a failure after deployment is a
difference between the edge and that server, and `serve.py` is the one that is wrong.

## What it costs

The sibling account runs eight sites inside a 20 USD monthly budget, most of it unused. This one
serves a larger tree - about 160MB, against 25,000 objects for the largest UN site - but the same
pattern: S3 storage, CloudFront requests and a certificate, all of them small at this traffic.
