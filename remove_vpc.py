import argparse

import boto3
from botocore.exceptions import ClientError

def collect_resources(ec2, vpc_id, region):
    """
    Gather and print resources to be deleted.
    Returns a dict of resources for later use.
    """
    resources = {}

    # Internet Gateway
    igw = ec2.describe_internet_gateways(
        Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
    ).get("InternetGateways", [])
    resources["InternetGateways"] = [{"InternetGatewayId": i["InternetGatewayId"]} for i in igw]

    # Subnets
    subs = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("Subnets", [])
    resources["Subnets"] = [{"SubnetId": s["SubnetId"], "CidrBlock": s["CidrBlock"]} for s in subs]

    # Route Tables
    rtbs = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("RouteTables", [])
    resources["RouteTables"] = [{"RouteTableId": r["RouteTableId"]} for r in rtbs if not any(a.get("Main", False) for a in r["Associations"])]

    # Network ACLs
    acls = ec2.describe_network_acls(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("NetworkAcls", [])
    resources["NetworkAcls"] = [{"NetworkAclId": a["NetworkAclId"]} for a in acls if not a["IsDefault"]]

    # Security Groups
    sgps = ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("SecurityGroups", [])
    resources["SecurityGroups"] = [{"GroupId": s["GroupId"], "GroupName": s["GroupName"]} for s in sgps if s["GroupName"] != "default"]

    print(f"\nResources in VPC {vpc_id} ({region}):")
    for k, v in resources.items():
        print(f"  {k}:")
        if v:
            for entry in v:
                print(f"    {entry}")
        else:
            print("    None found")
    print(f"\nResources in VPC {vpc_id} ({region}):")

    return resources

def prompt_continue():
    while True:
        user_input = input("Proceed with deleting these resources? [yes/NO]: ").strip().lower()
        if user_input in ("yes", "y"):
            return True
        elif user_input in ("no", "n", ""):
            return False
        else:
            print("Please enter yes or no.")


def delete_igw(ec2, vpc_id):
    """
    Detach and delete the internet gateway
    """

    args = {"Filters": [{"Name": "attachment.vpc-id", "Values": [vpc_id]}]}

    try:
        igw = ec2.describe_internet_gateways(**args)["InternetGateways"]
    except ClientError as e:
        print(e.response["Error"]["Message"])

    if igw:
        igw_id = igw[0]["InternetGatewayId"]

        try:
            result = ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        except ClientError as e:
            print(e.response["Error"]["Message"])

        try:
            result = ec2.delete_internet_gateway(InternetGatewayId=igw_id)
        except ClientError as e:
            print(e.response["Error"]["Message"])

    return


def delete_subs(ec2, args):
    """
    Delete the subnets
    """

    try:
        subs = ec2.describe_subnets(**args)["Subnets"]
    except ClientError as e:
        print(e.response["Error"]["Message"])

    if subs:
        for sub in subs:
            sub_id = sub["SubnetId"]

            try:
                result = ec2.delete_subnet(SubnetId=sub_id)
            except ClientError as e:
                print(e.response["Error"]["Message"])

    return


def delete_rtbs(ec2, args):
    """
    Delete the route tables
    """

    try:
        rtbs = ec2.describe_route_tables(**args)["RouteTables"]
    except ClientError as e:
        print(e.response["Error"]["Message"])

    if rtbs:
        for rtb in rtbs:
            main = "false"
            for assoc in rtb["Associations"]:
                main = assoc["Main"]
            if main == True:
                continue
            rtb_id = rtb["RouteTableId"]

            try:
                result = ec2.delete_route_table(RouteTableId=rtb_id)
            except ClientError as e:
                print(e.response["Error"]["Message"])

    return


def delete_acls(ec2, args):
    """
    Delete the network access lists (NACLs)
    """

    try:
        acls = ec2.describe_network_acls(**args)["NetworkAcls"]
    except ClientError as e:
        print(e.response["Error"]["Message"])

    if acls:
        for acl in acls:
            default = acl["IsDefault"]
            if default == True:
                continue
            acl_id = acl["NetworkAclId"]

            try:
                result = ec2.delete_network_acl(NetworkAclId=acl_id)
            except ClientError as e:
                print(e.response["Error"]["Message"])

    return


def delete_sgps(ec2, args):
    """
    Delete any security groups
    """

    try:
        sgps = ec2.describe_security_groups(**args)["SecurityGroups"]
    except ClientError as e:
        print(e.response["Error"]["Message"])

    if sgps:
        for sgp in sgps:
            default = sgp["GroupName"]
            if default == "default":
                continue
            sg_id = sgp["GroupId"]

            try:
                result = ec2.delete_security_group(GroupId=sg_id)
            except ClientError as e:
                print(e.response["Error"]["Message"])

    return


def delete_vpc(ec2, vpc_id, region):
    """
    Delete the VPC
    """

    try:
        result = ec2.delete_vpc(VpcId=vpc_id)
    except ClientError as e:
        print(e.response["Error"]["Message"])

    else:
        print(f'VPC {vpc_id} has been deleted from the {region} region.')

    return


def get_regions(ec2):
    """
    Return all AWS regions
    """

    regions = []

    try:
        aws_regions = ec2.describe_regions()["Regions"]
    except ClientError as e:
        print(e.response["Error"]["Message"])

    else:
        for region in aws_regions:
            regions.append(region["RegionName"])

    return regions


def main(profile):
    """
    Do the work..

    Order of operation:

    1.) Delete the internet gateway
    2.) Delete subnets
    3.) Delete route tables
    4.) Delete network access lists
    5.) Delete security groups
    6.) Delete the VPC
    """

    # AWS Credentials
    # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html

    session = boto3.Session(profile_name=profile)
    ec2 = session.client("ec2", region_name="us-east-1")

    regions = get_regions(ec2)

    for region in regions:

        ec2 = session.client("ec2", region_name=region)

        try:
            attribs = ec2.describe_account_attributes(AttributeNames=["default-vpc"])[
                "AccountAttributes"
            ]
        except ClientError as e:
            print(e.response["Error"]["Message"])
            return

        else:
            vpc_id = attribs[0]["AttributeValues"][0]["AttributeValue"]

        if vpc_id == "none":
            print(f'VPC (default) was not found in the {region} region.')
            continue

        # Are there any existing resources?  Since most resources attach an ENI, let's check..

        args = {"Filters": [{"Name": "vpc-id", "Values": [vpc_id]}]}

        try:
            eni = ec2.describe_network_interfaces(**args)["NetworkInterfaces"]
        except ClientError as e:
            print(e.response["Error"]["Message"])
            return

        if eni:
            print(f'VPC {vpc_id} has existing resources in the {region} region.')
            continue

        resources = collect_resources(ec2, vpc_id, region)
        if not prompt_continue():
            print(f"Skipping VPC {vpc_id} in region {region}.\n")
            continue

        result = delete_igw(ec2, vpc_id)
        result = delete_subs(ec2, args)
        result = delete_rtbs(ec2, args)
        result = delete_acls(ec2, args)
        result = delete_sgps(ec2, args)
        result = delete_vpc(ec2, vpc_id, region)

    return


if __name__ == "__main__":

    parser = argparse.ArgumentParser("Delete VPC's")
    parser.add_argument('-p', "--profile", help="AWS Profile you are logged into", type=str)
    args = parser.parse_args()

    aws_profile = args.profile
    print(f"AWS Profile set to {aws_profile}")

    main(profile=aws_profile)
