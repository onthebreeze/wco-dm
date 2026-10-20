#!/usr/bin/env python3
"""Fail if a deployed CloudFront Function differs from what this repository synthesises.

The pipeline builds the site, uploads it and invalidates the distribution. It does not deploy the
CDK, so an edit to a viewer-request or viewer-response function goes green and never reaches the
edge. That happened once already: a routing fix sat undeployed long enough that a version path like
/4.3.0/ was still being treated as a file extension and 404ing in production.

This closes that gap from the cheap side. `cdk synth` needs no AWS access at all, and comparing its
function code against the live code needs only cloudfront:GetFunction, rather than the
CloudFormation privileges a full `cdk diff` would require on a deliberately minimal deploy role.

    python3 deploy/aws/check-function-drift.py <stack> [--profile NAME]

Exit 0 when every function matches, 1 on drift, 2 if something could not be checked.
"""
import argparse, json, os, subprocess, sys

def synthesised(stack, cdk_dir):
    """Run cdk synth and return {FunctionName: FunctionCode} from the template."""
    template = os.path.join(cdk_dir, 'cdk.out', f'{stack}.template.json')
    subprocess.run(['npx', 'cdk', 'synth', stack, '--quiet'], cwd=cdk_dir,
                   check=True, stdout=subprocess.DEVNULL)
    doc = json.load(open(template))
    out = {}
    for logical, res in doc.get('Resources', {}).items():
        if res.get('Type') != 'AWS::CloudFront::Function':
            continue
        props = res['Properties']
        name, code = props.get('Name'), props.get('FunctionCode')
        if not isinstance(name, str) or not isinstance(code, str):
            # A name built by Fn::Join cannot be resolved without deploying; skip rather than guess.
            print(f"  ? {logical}: name or code is not a literal, skipped")
            continue
        out[name] = code
    return out

def live(name, session):
    r = session.get_function(Name=name, Stage='LIVE')
    return r['FunctionCode'].read().decode('utf-8')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stack')
    ap.add_argument('--profile')
    ap.add_argument('--cdk-dir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cdk'))
    a = ap.parse_args()

    import boto3
    s = boto3.Session(profile_name=a.profile) if a.profile else boto3.Session()
    cf = s.client('cloudfront')

    want = synthesised(a.stack, os.path.normpath(a.cdk_dir))
    if not want:
        print('No CloudFront Functions found in the synthesised template.')
        return 2

    drifted, missing = [], []
    for name, code in sorted(want.items()):
        try:
            current = live(name, cf)
        except cf.exceptions.NoSuchFunctionExists:
            missing.append(name)
            print(f'  ! {name}: not deployed')
            continue
        if current.strip() == code.strip():
            print(f'  ok {name}')
        else:
            drifted.append(name)
            print(f'  DRIFT {name}: the deployed code differs from this repository')

    if drifted or missing:
        print()
        print(f'{len(drifted)} function(s) drifted, {len(missing)} not deployed.')
        print('The pipeline does not deploy the CDK. Run:')
        print(f'  cd deploy/cdk && npx cdk deploy {a.stack}' + (f' --profile {a.profile}' if a.profile else ''))
        return 1

    print(f'\n{len(want)} function(s) match the deployed code.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
