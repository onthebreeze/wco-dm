import * as fs from 'fs';
import * as path from 'path';
import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps, Tags } from 'aws-cdk-lib';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import {
  BRANCH, BUCKET, EXCLUDE_FROM_SEARCH, FORMATS, GITHUB_ISSUER, HOSTNAME, PRODUCTION, REPOSITORY,
  SUBJECT,
} from './config';

export interface SiteStackProps extends StackProps {
  readonly certificate: acm.ICertificate;
}

/**
 * The site: a private bucket, a CloudFront distribution in front of it, the two edge functions,
 * and the role GitHub Actions assumes to deploy. Nothing runs at request time but the functions.
 *
 * This is the same shape as the UN/CEFACT standards sites, and the two edge functions are the same
 * files, because the routing rule is the same rule. What differs is the forge: those sites are
 * deployed from GitLab job tokens, this one from a GitHub Actions token.
 */
export class SiteStack extends Stack {
  constructor(scope: Construct, id: string, props: SiteStackProps) {
    super(scope, id, props);
    const { certificate } = props;

    Tags.of(this).add('site', 'wcodm');
    Tags.of(this).add('hostname', HOSTNAME);

    const bucket = new s3.Bucket(this, 'Content', {
      bucketName: BUCKET,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      // Everything in it is generated from the workbooks by one command, so it is disposable.
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const router = new cloudfront.Function(this, 'Router', {
      functionName: 'wcodm-router',
      runtime: cloudfront.FunctionRuntime.JS_2_0,
      comment: `Routing and Accept negotiation for ${HOSTNAME}`,
      code: cloudfront.FunctionCode.fromInline(
        this.renderFunction('router.js', {
          __NEGOTIATE__: 'true',
          __FORMATS__: JSON.stringify(FORMATS),
          __WHOLE_GRAPH__: '',
          __EXCLUDE_FROM_SEARCH__: EXCLUDE_FROM_SEARCH ? 'true' : 'false',
        }),
      ),
    });

    const headers = new cloudfront.Function(this, 'Headers', {
      functionName: 'wcodm-headers',
      runtime: cloudfront.FunctionRuntime.JS_2_0,
      comment: `Representation presentation rules for ${HOSTNAME}`,
      code: cloudfront.FunctionCode.fromInline(this.renderFunction('headers.js', {})),
    });
    // CloudFront rate-limits CreateFunction. Two is well inside it, but creating them in sequence
    // costs nothing and removes the failure mode entirely.
    headers.node.addDependency(router);

    // Accept is deliberately absent from the cache key. The viewer-request function rewrites the
    // URI to a concrete representation before the cache is consulted, so the four representations
    // are already distinct entries. Including Accept would shatter the cache across every
    // browser's Accept string for no benefit.
    const cachePolicy = new cloudfront.CachePolicy(this, 'Cache', {
      cachePolicyName: 'wcodm',
      comment: 'URI-only cache key; negotiation happens in the viewer-request function',
      defaultTtl: Duration.minutes(5),
      minTtl: Duration.seconds(0),
      maxTtl: Duration.days(1),
      headerBehavior: cloudfront.CacheHeaderBehavior.none(),
      queryStringBehavior: cloudfront.CacheQueryStringBehavior.none(),
      cookieBehavior: cloudfront.CacheCookieBehavior.none(),
      enableAcceptEncodingGzip: true,
      enableAcceptEncodingBrotli: true,
    });

    const customHeaders: cloudfront.ResponseCustomHeader[] = [
      // One address returns HTML, Turtle, JSON-LD or RDF/XML. Downstream caches need to know.
      { header: 'Vary', value: 'Accept', override: true },
    ];
    if (EXCLUDE_FROM_SEARCH) {
      // Set at the edge rather than in the build, so it cannot be forgotten in a repository and
      // cannot travel with a build artefact into another environment.
      customHeaders.push({ header: 'X-Robots-Tag', value: 'noindex, nofollow', override: true });
    }
    const responseHeaders = new cloudfront.ResponseHeadersPolicy(this, 'ResponseHeaders', {
      responseHeadersPolicyName: 'wcodm',
      customHeadersBehavior: { customHeaders },
      corsBehavior: {
        accessControlAllowOrigins: ['*'],
        accessControlAllowHeaders: ['*'],
        accessControlAllowMethods: ['GET', 'HEAD', 'OPTIONS'],
        accessControlAllowCredentials: false,
        originOverride: true,
      },
    });

    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      comment: `${HOSTNAME} (unofficial rendering; production would be ${PRODUCTION})`,
      domainNames: [HOSTNAME],
      certificate,
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(bucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        compress: true,
        cachePolicy,
        responseHeadersPolicy: responseHeaders,
        functionAssociations: [
          { function: router, eventType: cloudfront.FunctionEventType.VIEWER_REQUEST },
          { function: headers, eventType: cloudfront.FunctionEventType.VIEWER_RESPONSE },
        ],
      },
      errorResponses: [
        // A negotiated miss lands here too, which is the right answer: an unknown term has no
        // representation in any format.
        { httpStatus: 403, responseHttpStatus: 404, responsePagePath: '/404.html' },
        { httpStatus: 404, responseHttpStatus: 404, responsePagePath: '/404.html' },
      ],
      priceClass: cloudfront.PriceClass.PRICE_CLASS_ALL,
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      enableIpv6: true,
    });

    // GitHub, as the issuer of the workflow tokens. One provider, one role, and the sub claim pins
    // the repository and the branch, so a workflow in another repository, or on another branch of
    // this one, cannot assume it. No long-lived AWS credentials exist in this account.
    const oidcProvider = new iam.OpenIdConnectProvider(this, 'GitHub', {
      url: GITHUB_ISSUER,
      clientIds: ['sts.amazonaws.com'],
    });

    const deployRole = new iam.Role(this, 'DeployRole', {
      roleName: 'github-deploy-wcodm',
      description: `Deploys ${REPOSITORY}:${BRANCH} to ${HOSTNAME}`,
      maxSessionDuration: Duration.hours(1),
      assumedBy: new iam.WebIdentityPrincipal(oidcProvider.openIdConnectProviderArn, {
        StringEquals: {
          'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
          'token.actions.githubusercontent.com:sub': SUBJECT,
        },
      }),
    });

    bucket.grantReadWrite(deployRole);
    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['cloudfront:CreateInvalidation', 'cloudfront:GetInvalidation'],
        resources: [`arn:aws:cloudfront::${this.account}:distribution/${distribution.distributionId}`],
      }),
    );

    // Read-only, so that the pipeline can check whether the deployed viewer functions still match
    // this repository. The pipeline does not deploy the CDK, so a function edit otherwise goes
    // green and never reaches the edge. Comparing synthesised code against live code needs this one
    // permission; a full `cdk diff` would need CloudFormation rights this role should not have.
    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['cloudfront:GetFunction', 'cloudfront:DescribeFunction'],
        resources: [`arn:aws:cloudfront::${this.account}:function/*`],
      }),
    );

    new CfnOutput(this, 'Bucket', { value: bucket.bucketName });
    new CfnOutput(this, 'DistributionId', { value: distribution.distributionId });
    new CfnOutput(this, 'DistributionDomain', { value: distribution.distributionDomainName });
    new CfnOutput(this, 'DeployRoleArn', { value: deployRole.roleArn });
  }

  /**
   * Read a function source and substitute its synth-time placeholders. CloudFront Functions take
   * no environment variables, so configuration has to be baked into the source.
   */
  private renderFunction(file: string, substitutions: Record<string, string>): string {
    let code = fs.readFileSync(path.join(__dirname, '..', 'functions', file), 'utf8');
    for (const [token, value] of Object.entries(substitutions)) {
      code = code.split(token).join(value);
    }
    if (Buffer.byteLength(code, 'utf8') > 10240) {
      throw new Error(`${file} exceeds the 10 KB CloudFront Functions limit after substitution`);
    }
    return code;
  }
}
