#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CertificateStack } from '../lib/certificate-stack';
import { SiteStack } from '../lib/site-stack';

const account = process.env.CDK_DEPLOY_ACCOUNT ?? process.env.CDK_DEFAULT_ACCOUNT;
const region = process.env.CDK_DEPLOY_REGION ?? 'ap-southeast-2';

const app = new cdk.App();

const certificate = new CertificateStack(app, 'WcoTestCertificate', {
  env: { account, region: 'us-east-1' },
  description: 'Certificate for the WCO Data Model vocabulary test site',
  crossRegionReferences: true,
});

new SiteStack(app, 'WcoTestSite', {
  env: { account, region },
  description: 'Bucket, distribution, edge functions and the GitHub deploy role',
  crossRegionReferences: true,
  certificate: certificate.certificate,
});

cdk.Tags.of(app).add('environment', 'wco-test');
cdk.Tags.of(app).add('managed-by', 'wco-dm/deploy/cdk');
