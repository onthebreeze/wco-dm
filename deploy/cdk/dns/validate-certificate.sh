#!/usr/bin/env bash
# Create the DNS record that validates the certificate.
#
# The certificate is issued in wco-test; the hosted zone is in the management account. Nothing can
# do both halves with one set of credentials, so this reads the pending validation record with the
# site profile and writes it with the management profile.
#
# Run it while `cdk deploy WcoTestCertificate` is sitting in CREATE_IN_PROGRESS: that is
# CloudFormation waiting for exactly this record.
#
#   SITE_PROFILE=wco-test MGMT_PROFILE=default ./validate-certificate.sh
set -euo pipefail

SITE_PROFILE="${SITE_PROFILE:-wco-test}"
MGMT_PROFILE="${MGMT_PROFILE:-default}"
ZONE_ID="${ZONE_ID:-Z0512956MDZ08WHZBJGA}"
HOSTNAME="${HOSTNAME:-test-wcodm.trade-commons.org}"

arn=$(aws acm list-certificates --profile "$SITE_PROFILE" --region us-east-1 \
  --query "CertificateSummaryList[?DomainName=='$HOSTNAME'].CertificateArn | [0]" \
  --output text)
[ "$arn" != "None" ] || { echo "no certificate for $HOSTNAME in $SITE_PROFILE/us-east-1" >&2; exit 1; }
echo "certificate: $arn"

records=$(aws acm describe-certificate --profile "$SITE_PROFILE" --region us-east-1 \
  --certificate-arn "$arn" \
  --query 'Certificate.DomainValidationOptions[?ResourceRecord!=null].ResourceRecord' \
  --output json | python3 -c '
import json, sys
seen, out = set(), []
for r in json.load(sys.stdin):
    if r["Name"] in seen:
        continue
    seen.add(r["Name"])
    out.append({"Action": "UPSERT", "ResourceRecordSet": {
        "Name": r["Name"], "Type": r["Type"], "TTL": 300,
        "ResourceRecords": [{"Value": r["Value"]}]}})
if not out:
    sys.exit("the certificate reports no validation records yet; wait for CREATE_IN_PROGRESS")
print(json.dumps({"Comment": "ACM validation for the WCO Data Model test site", "Changes": out}))')

echo "$records" | python3 -c 'import json,sys; [print(c["ResourceRecordSet"]["Name"]) for c in json.load(sys.stdin)["Changes"]]'
aws route53 change-resource-record-sets --profile "$MGMT_PROFILE" \
  --hosted-zone-id "$ZONE_ID" --change-batch "$records" \
  --query 'ChangeInfo.[Id,Status]' --output text
