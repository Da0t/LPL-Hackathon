"""Resumable single-instance AWS demo deployment. Run with authorized AWS credentials.

This deliberately uses one EC2 instance: the case workflow is SQLite backed and
must remain on a persistent disk. CloudFront gives the demo an HTTPS URL. This is
for synthetic hackathon records, not a highly available production deployment.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "var/deployment-aws.json"
PORTAL = json.loads((ROOT / "var/portal-aws.json").read_text())
KB = json.loads((ROOT / "var/knowledge-base.json").read_text())
GUARDRAIL_PATH = ROOT / "var/guardrail-aws.json"
GUARDRAIL = json.loads(GUARDRAIL_PATH.read_text()) if GUARDRAIL_PATH.exists() else None
REGION = "us-east-1"
MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"
PROFILE = "CoherentDemoWebProfile"
ROLE = "CoherentDemoWebRole"
SG_NAME = "coherent-demo-cloudfront-origin"
TAGS = [{"Key": "Project", "Value": "Coherent-Hackathon"}, {"Key": "Data", "Value": "SyntheticOnly"}]
state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
session = boto3.Session(region_name=REGION)
ec2, iam, ssm, cf = (session.client(x) for x in ("ec2", "iam", "ssm", "cloudfront"))
account = session.client("sts").get_caller_identity()["Account"]


def save():
    STATE_PATH.parent.mkdir(exist_ok=True)
    fd = os.open(STATE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")


def wait_until(label, ready, *, attempts=40, delay=15):
    for _ in range(attempts):
        value = ready()
        if value:
            return value
        print(f"Waiting for {label}...", flush=True)
        time.sleep(delay)
    raise TimeoutError(f"Timed out waiting for {label}")


def check_existing():
    if PORTAL["region"] != REGION or KB["region"] != REGION:
        raise RuntimeError("Portal and knowledge base must be in us-east-1")
    if session.client("dynamodb").describe_table(TableName=PORTAL["table_name"])["Table"]["TableStatus"] != "ACTIVE":
        raise RuntimeError("Client portal DynamoDB table is not active")
    session.client("cognito-idp").describe_user_pool(UserPoolId=PORTAL["user_pool_id"])
    kb = session.client("bedrock-agent").get_knowledge_base(knowledgeBaseId=KB["knowledge_base_id"])["knowledgeBase"]
    if kb["status"] != "ACTIVE":
        raise RuntimeError("Compliance knowledge base is not active")
    if GUARDRAIL:
        guardrail = session.client("bedrock").get_guardrail(guardrailIdentifier=GUARDRAIL["guardrail_id"], guardrailVersion=GUARDRAIL["version"])
        if guardrail["status"] != "READY":
            raise RuntimeError("Configured Bedrock Guardrail is not ready")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if status:
        raise RuntimeError("Commit and push deployment changes before deploying")
    remote_sha = subprocess.check_output(["git", "ls-remote", "origin", "refs/heads/main"], cwd=ROOT, text=True).split()[0]
    if sha != remote_sha:
        raise RuntimeError("Deployment must run from the pushed main commit")
    return sha


def ensure_instance_role():
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
    try:
        iam.get_role(RoleName=ROLE)
    except iam.exceptions.NoSuchEntityException:
        iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(trust), Tags=TAGS)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"], "Resource": f"arn:aws:dynamodb:{REGION}:{account}:table/{PORTAL['table_name']}"},
            {"Effect": "Allow", "Action": ["cognito-idp:InitiateAuth", "cognito-idp:GetUser", "cognito-idp:GlobalSignOut"], "Resource": f"arn:aws:cognito-idp:{REGION}:{account}:userpool/{PORTAL['user_pool_id']}"},
            {"Effect": "Allow", "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], "Resource": [
                f"arn:aws:bedrock:{REGION}:{account}:inference-profile/us.{MODEL}",
                f"arn:aws:bedrock:*::foundation-model/{MODEL}",
            ]},
            {"Effect": "Allow", "Action": "bedrock:Retrieve", "Resource": f"arn:aws:bedrock:{REGION}:{account}:knowledge-base/{KB['knowledge_base_id']}"},
            {"Effect": "Allow", "Action": "polly:SynthesizeSpeech", "Resource": "*"},
            *([{"Effect": "Allow", "Action": "bedrock:ApplyGuardrail", "Resource": f"arn:aws:bedrock:{REGION}:{account}:guardrail/{GUARDRAIL['guardrail_id']}"}] if GUARDRAIL else []),
        ],
    }
    iam.put_role_policy(RoleName=ROLE, PolicyName="CoherentDemoRuntime", PolicyDocument=json.dumps(policy))
    ssm_policy = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    if not any(x["PolicyArn"] == ssm_policy for x in iam.list_attached_role_policies(RoleName=ROLE)["AttachedPolicies"]):
        iam.attach_role_policy(RoleName=ROLE, PolicyArn=ssm_policy)
    try:
        iam.get_instance_profile(InstanceProfileName=PROFILE)
    except iam.exceptions.NoSuchEntityException:
        iam.create_instance_profile(InstanceProfileName=PROFILE, Tags=TAGS)
    profile = iam.get_instance_profile(InstanceProfileName=PROFILE)["InstanceProfile"]
    if not any(r["RoleName"] == ROLE for r in profile["Roles"]):
        iam.add_role_to_instance_profile(InstanceProfileName=PROFILE, RoleName=ROLE)
    print("Scoped EC2 role and Systems Manager access ready", flush=True)


def ensure_network():
    prefix = ec2.describe_managed_prefix_lists(Filters=[{"Name": "prefix-list-name", "Values": ["com.amazonaws.global.cloudfront.origin-facing"]}])["PrefixLists"][0]["PrefixListId"]
    if not state.get("security_group_id"):
        vpc = next(v for v in ec2.describe_vpcs()["Vpcs"] if v.get("IsDefault"))
        group = ec2.create_security_group(GroupName=SG_NAME, Description="CloudFront only for Coherent demo", VpcId=vpc["VpcId"], TagSpecifications=[{"ResourceType": "security-group", "Tags": TAGS}])
        state["security_group_id"] = group["GroupId"]
        save()
    group = ec2.describe_security_groups(GroupIds=[state["security_group_id"]])["SecurityGroups"][0]
    if not any(any(p["PrefixListId"] == prefix for p in rule.get("PrefixListIds", [])) for rule in group["IpPermissions"]):
        ec2.authorize_security_group_ingress(GroupId=group["GroupId"], IpPermissions=[{"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "PrefixListIds": [{"PrefixListId": prefix, "Description": "CloudFront origin-facing only"}]}])
    if not state.get("allocation_id"):
        allocation = ec2.allocate_address(Domain="vpc", TagSpecifications=[{"ResourceType": "elastic-ip", "Tags": TAGS}])
        state["allocation_id"] = allocation["AllocationId"]
        state["public_ip"] = allocation["PublicIp"]
        save()
    print("CloudFront-restricted security group and static origin address ready", flush=True)


def ensure_instance():
    if not state.get("instance_id"):
        images = ec2.describe_images(Owners=["amazon"], Filters=[{"Name": "name", "Values": ["al2023-ami-2023.*-x86_64"]}, {"Name": "state", "Values": ["available"]}])["Images"]
        ami = max(images, key=lambda x: x["CreationDate"])
        subnet = next(s for s in ec2.describe_subnets()["Subnets"] if s["AvailabilityZone"] == "us-east-1a")
        kwargs = dict(
            ImageId=ami["ImageId"], InstanceType="t3.large", MinCount=1, MaxCount=1,
            SubnetId=subnet["SubnetId"], SecurityGroupIds=[state["security_group_id"]],
            IamInstanceProfile={"Name": PROFILE},
            MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled"},
            BlockDeviceMappings=[{"DeviceName": ami["RootDeviceName"], "Ebs": {"VolumeSize": 30, "VolumeType": "gp3", "Encrypted": True, "DeleteOnTermination": True}}],
            TagSpecifications=[{"ResourceType": "instance", "Tags": TAGS + [{"Key": "Name", "Value": "CoherentDemoWeb"}]}],
        )
        # IAM instance-profile propagation is eventually consistent.
        for attempt in range(6):
            try:
                instance = ec2.run_instances(**kwargs)["Instances"][0]
                break
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(10)
        state["instance_id"] = instance["InstanceId"]
        save()
    ec2.get_waiter("instance_running").wait(InstanceIds=[state["instance_id"]])
    address = ec2.describe_addresses(AllocationIds=[state["allocation_id"]])["Addresses"][0]
    if address.get("InstanceId") != state["instance_id"]:
        ec2.associate_address(AllocationId=state["allocation_id"], InstanceId=state["instance_id"])
    instance = ec2.describe_instances(InstanceIds=[state["instance_id"]])["Reservations"][0]["Instances"][0]
    state["public_dns"] = instance.get("PublicDnsName") or f"ec2-{state['public_ip'].replace('.', '-')}.compute-1.amazonaws.com"
    save()
    print("EC2 host running with encrypted persistent disk and no SSH access", flush=True)


def ensure_cloudfront():
    if not state.get("origin_token"):
        state["origin_token"] = secrets.token_hex(32)
        save()
    if not state.get("distribution_id"):
        config = {
            "CallerReference": f"coherent-demo-{int(time.time())}",
            "Origins": {"Quantity": 1, "Items": [{
                "Id": "coherent-ec2", "DomainName": state["public_dns"],
                "CustomHeaders": {"Quantity": 1, "Items": [{"HeaderName": "X-Coherent-Origin", "HeaderValue": state["origin_token"]}]},
                "CustomOriginConfig": {"HTTPPort": 80, "HTTPSPort": 443, "OriginProtocolPolicy": "http-only", "OriginReadTimeout": 120},
            }]},
            "DefaultCacheBehavior": {
                "TargetOriginId": "coherent-ec2", "ViewerProtocolPolicy": "redirect-to-https",
                "AllowedMethods": {"Quantity": 7, "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"], "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}},
                "Compress": True,
                "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",  # AWS managed CachingDisabled
                "OriginRequestPolicyId": "216adef6-5c7f-47e4-b989-5492eafa07d3",  # AWS managed AllViewer
            },
            "Comment": "Coherent synthetic-data hackathon demo",
            "Enabled": True, "PriceClass": "PriceClass_100",
            "ViewerCertificate": {"CloudFrontDefaultCertificate": True},
            "IsIPV6Enabled": True,
        }
        result = cf.create_distribution(DistributionConfig=config)["Distribution"]
        state["distribution_id"] = result["Id"]
        state["distribution_domain"] = result["DomainName"]
        save()
    print("CloudFront HTTPS distribution ready:", state["distribution_domain"], flush=True)


def install(sha):
    needs_command = not state.get("ssm_command_id") or state.get("command_sha") != sha
    if not needs_command and state.get("deployed_sha") != sha:
        try:
            previous = ssm.get_command_invocation(CommandId=state["ssm_command_id"], InstanceId=state["instance_id"])
            needs_command = previous["Status"] in ("Failed", "Cancelled", "TimedOut")
        except ssm.exceptions.InvocationDoesNotExist:
            pass
    if needs_command:
        def online():
            rows = ssm.describe_instance_information(Filters=[{"Key": "InstanceIds", "Values": [state["instance_id"]]}])["InstanceInformationList"]
            return bool(rows and rows[0]["PingStatus"] == "Online")
        wait_until("Systems Manager agent", online, attempts=30)
        installer = ROOT / "scripts/install_aws_host.sh"
        digest = hashlib.sha256(installer.read_bytes()).hexdigest()
        config_b64 = base64.b64encode(json.dumps(PORTAL).encode()).decode()
        command = f"""set -e
curl --fail --silent --show-error --location 'https://raw.githubusercontent.com/Da0t/LPL-Hackathon/{sha}/scripts/install_aws_host.sh' -o /tmp/install-coherent.sh
echo '{digest}  /tmp/install-coherent.sh' | sha256sum -c -
COHERENT_GIT_SHA='{sha}' COHERENT_PUBLIC_ORIGIN='https://{state['distribution_domain']}' COHERENT_ORIGIN_TOKEN='{state['origin_token']}' COHERENT_PORTAL_CONFIG_B64='{config_b64}' COHERENT_KB_ID='{KB['knowledge_base_id']}' COHERENT_GUARDRAIL_ID='{GUARDRAIL['guardrail_id'] if GUARDRAIL else ''}' COHERENT_GUARDRAIL_VERSION='{GUARDRAIL['version'] if GUARDRAIL else ''}' bash /tmp/install-coherent.sh
"""
        result = ssm.send_command(InstanceIds=[state["instance_id"]], DocumentName="AWS-RunShellScript", Parameters={"commands": [command], "executionTimeout": ["3600"]}, TimeoutSeconds=3600, Comment="Install pinned Coherent demo release")
        state["ssm_command_id"] = result["Command"]["CommandId"]
        state["command_sha"] = sha
        save()
    def finished():
        try:
            item = ssm.get_command_invocation(CommandId=state["ssm_command_id"], InstanceId=state["instance_id"])
        except ssm.exceptions.InvocationDoesNotExist:
            return False
        if item["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
            return item
        return False
    result = wait_until("host build and startup", finished, attempts=120)
    if result["Status"] != "Success":
        print(result.get("StandardOutputContent", "")[-4000:])
        print(result.get("StandardErrorContent", "")[-4000:])
        raise RuntimeError(f"Host install {result['Status']}")
    state["deployed_sha"] = sha
    save()
    print(result.get("StandardOutputContent", "")[-1000:])


def main():
    sha = check_existing()
    ensure_instance_role()
    ensure_network()
    ensure_instance()
    ensure_cloudfront()
    install(sha)
    def deployed():
        return cf.get_distribution(Id=state["distribution_id"])["Distribution"]["Status"] == "Deployed"
    wait_until("CloudFront deployment", deployed, attempts=40)
    print("LIVE_URL=https://" + state["distribution_domain"] + "/login")


if __name__ == "__main__":
    main()
