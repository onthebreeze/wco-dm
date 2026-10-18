import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';
import { HOSTNAME } from './config';

/**
 * The certificate, in us-east-1 because CloudFront accepts no other region.
 *
 * One name, not a wildcard: this account serves one site, and a certificate that covered the whole
 * domain would be a credential for names that belong to a different deployment.
 *
 * Validation is by DNS and the records have to be written by hand, because the hosted zone is in
 * the management account and this stack deploys into wco-test. CloudFormation waits in
 * CREATE_IN_PROGRESS until they resolve, so deploy this stack first and run
 * dns/validate-certificate.sh while it waits.
 */
export class CertificateStack extends Stack {
  readonly certificate: acm.Certificate;

  constructor(scope: Construct, id: string, props: StackProps) {
    super(scope, id, props);

    this.certificate = new acm.Certificate(this, 'Site', {
      domainName: HOSTNAME,
      validation: acm.CertificateValidation.fromDns(),
    });

    new CfnOutput(this, 'CertificateArn', { value: this.certificate.certificateArn });
  }
}
