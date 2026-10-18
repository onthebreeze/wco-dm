#!/usr/bin/env bash
# Point the hostname at its CloudFront distribution.
#
# The distribution is in wco-test and the hosted zone is in the management account, so this reads
# the deployed distribution with the site profile and writes the alias records with the management
# profile. Run it after `cdk deploy WcoTestSite`, and again only if the distribution is ever
# replaced; ordinary content deploys do not change these records.
#
#   SITE_PROFILE=wco-test MGMT_PROFILE=default ./upsert-site-record.sh
set -euo pipefail

SITE_PROFILE="${SITE_PROFILE:-wco-test}"
MGMT_PROFILE="${MGMT_PROFILE:-default}"
ZONE_ID="${ZONE_ID:-Z0512956MDZ08WHZBJGA}"
HOSTNAME="${HOSTNAME:-test-wcodm.trade-commons.org}"
# The fixed hosted zone id every CloudFront distribution aliases to. Not a per-account value.
CLOUDFRONT_ZONE="Z2FDTNDATAQYW2"

changes=$(aws cloudfront list-distributions --profile "$SITE_PROFILE" \
  --query 'DistributionList.Items[].{alias: Aliases.Items[0], domain: DomainName}' \
  --output json | CF_ZONE="$CLOUDFRONT_ZONE" WANT="$HOSTNAME" python3 -c '
import json, os, sys
zone, want = os.environ["CF_ZONE"], os.environ["WANT"]
changes = []
for d in json.load(sys.stdin) or []:
    if d.get("alias") != want:
        continue
    for rtype in ("A", "AAAA"):
        changes.append({"Action": "UPSERT", "ResourceRecordSet": {
            "Name": want, "Type": rtype,
            "AliasTarget": {"HostedZoneId": zone, "DNSName": d["domain"],
                            "EvaluateTargetHealth": False}}})
if not changes:
    sys.exit(f"no distribution aliased to {want} found")
print(json.dumps({"Comment": "WCO Data Model test site alias", "Changes": changes}))')

echo "$changes" | python3 -c 'import json,sys; [print(c["ResourceRecordSet"]["Type"], c["ResourceRecordSet"]["Name"], "->", c["ResourceRecordSet"]["AliasTarget"]["DNSName"]) for c in json.load(sys.stdin)["Changes"]]'
aws route53 change-resource-record-sets --profile "$MGMT_PROFILE" \
  --hosted-zone-id "$ZONE_ID" --change-batch "$changes" \
  --query 'ChangeInfo.[Id,Status]' --output text
