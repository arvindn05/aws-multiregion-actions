"""

Remove those pesky AWS default VPCs.

Python Version: 3.7.0
Boto3 Version: 1.7.50

"""

import argparse
import operator
from functools import reduce

import boto3
from botocore.exceptions import ClientError


def getitem(d, key):
    return reduce(operator.getitem, key, d)


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

    # AWS Credentials
    # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html

    session = boto3.Session(profile_name=profile)
    ec2 = session.client("ec2", region_name="us-east-1")

    regions = get_regions(ec2)
    # regions = ['us-east-1']

    for region in regions:

        athena = session.client("athena", region_name=region)

        try:
            workgroup = athena.get_work_group(WorkGroup="primary")
            if workgroup:
                print(f'Primary workgroup found in the {region} region.')
                client_setting = getitem(
                    workgroup,
                    ("WorkGroup", "Configuration", "EnforceWorkGroupConfiguration"),
                )
                if not client_setting:
                    result = athena.update_work_group(
                        WorkGroup="primary",
                        ConfigurationUpdates={"EnforceWorkGroupConfiguration": True},
                    )
                    response_code = getitem(
                        result, ("ResponseMetadata", "HTTPStatusCode")
                    )
                    print(
                        f'Primary workgroup setting updated in the {region} region with result {response_code}'
                    )
                else:
                    print(
                        f'Primary workgroup setting NOT updated in the {region} region as its already set'
                    )
        except ClientError as e:
            print(e.response["Error"]["Message"])
            return

    return


if __name__ == "__main__":

    parser = argparse.ArgumentParser("Set Athena Client settings")
    parser.add_argument('-p', "--profile", help="AWS Profile you are logged into", type=str)
    args = parser.parse_args()

    aws_profile = args.profile
    print(f"AWS Profile set to {aws_profile}")
    main(profile=aws_profile)
