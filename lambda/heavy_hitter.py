"""
AWS Nuclear Button — Heavy Hitter Termination Script
=====================================================
This Lambda function is the PRIMARY immediate responder. It is triggered
directly by an SNS notification the moment your AWS Budget threshold
is breached. It fires FIRST, before any other cleanup (like aws-nuke).

It scans ALL enabled AWS regions and terminates/deletes the top cost-
generating services:
  1. EC2 Instances (running)
  2. RDS Databases
  3. NAT Gateways
  4. EKS Clusters (+ node groups)
  5. Elastic IPs (unattached AND attached)
  6. SageMaker Notebook Instances
  7. Elastic Load Balancers (ALB/NLB/CLB)
  8. EBS Volumes (unattached)

Author:  Your Name
Project: AWS Nuclear Button — Hybrid Kill Switch
License: MIT
"""

import boto3
import json
import logging

# ---------- Configuration ----------
# Set to True to only LOG what would be deleted (safe mode)
DRY_RUN = False

# Tags to protect: instances with these tags will NOT be terminated
# Example: {"Project": "keep-alive"} would protect anything tagged Project=keep-alive
PROTECTED_TAGS = {}

# Primary region — scanned FIRST before all others
PRIMARY_REGION = "ap-south-1"  # Mumbai

# Regions to skip (if any). Leave empty to scan all enabled regions.
SKIP_REGIONS = []

# ---------- Logging Setup ----------
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_all_regions():
    """Discover all enabled AWS regions, with PRIMARY_REGION first."""
    ec2 = boto3.client("ec2", region_name=PRIMARY_REGION)
    regions = ec2.describe_regions(
        Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}]
    )
    all_regions = [r["RegionName"] for r in regions["Regions"] if r["RegionName"] not in SKIP_REGIONS]

    # Ensure PRIMARY_REGION is scanned first
    if PRIMARY_REGION in all_regions:
        all_regions.remove(PRIMARY_REGION)
        all_regions.insert(0, PRIMARY_REGION)

    return all_regions


def is_protected(tags):
    """Check if a resource's tags match any protected tag."""
    if not PROTECTED_TAGS or not tags:
        return False
    tag_dict = {t["Key"]: t["Value"] for t in tags}
    for key, value in PROTECTED_TAGS.items():
        if tag_dict.get(key) == value:
            return True
    return False


def terminate_ec2_instances(region):
    """Find and terminate all running EC2 instances in a region."""
    ec2 = boto3.client("ec2", region_name=region)
    terminated = []

    try:
        response = ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["running", "stopped"]}]
        )
        instance_ids = []
        for reservation in response["Reservations"]:
            for instance in reservation["Instances"]:
                if is_protected(instance.get("Tags", [])):
                    logger.info(f"  [PROTECTED] Skipping EC2 {instance['InstanceId']}")
                    continue
                instance_ids.append(instance["InstanceId"])

        if instance_ids:
            if DRY_RUN:
                logger.info(f"  [DRY-RUN] Would terminate EC2: {instance_ids}")
            else:
                # Disable termination protection first
                for iid in instance_ids:
                    try:
                        ec2.modify_instance_attribute(
                            InstanceId=iid,
                            DisableApiTermination={"Value": False}
                        )
                    except Exception:
                        pass  # If we can't modify, try terminating anyway

                ec2.terminate_instances(InstanceIds=instance_ids)
                logger.info(f"  ✅ Terminated EC2: {instance_ids}")
                terminated = instance_ids
    except Exception as e:
        logger.error(f"  ❌ EC2 error in {region}: {str(e)}")

    return terminated


def delete_rds_instances(region):
    """Find and delete all RDS database instances in a region."""
    rds = boto3.client("rds", region_name=region)
    deleted = []

    try:
        response = rds.describe_db_instances()
        for db in response["DBInstances"]:
            db_id = db["DBInstanceIdentifier"]
            if db["DBInstanceStatus"] in ("available", "stopped", "backing-up", "creating"):
                if DRY_RUN:
                    logger.info(f"  [DRY-RUN] Would delete RDS: {db_id}")
                else:
                    try:
                        # Disable deletion protection first
                        rds.modify_db_instance(
                            DBInstanceIdentifier=db_id,
                            DeletionProtection=False
                        )
                    except Exception:
                        pass

                    rds.delete_db_instance(
                        DBInstanceIdentifier=db_id,
                        SkipFinalSnapshot=True,
                        DeleteAutomatedBackups=True
                    )
                    logger.info(f"  ✅ Deleting RDS: {db_id}")
                    deleted.append(db_id)
    except Exception as e:
        logger.error(f"  ❌ RDS error in {region}: {str(e)}")

    return deleted


def delete_nat_gateways(region):
    """Find and delete all NAT Gateways (~$30/month just for existing)."""
    ec2 = boto3.client("ec2", region_name=region)
    deleted = []

    try:
        response = ec2.describe_nat_gateways(
            Filters=[{"Name": "state", "Values": ["available", "pending"]}]
        )
        for nat in response["NatGateways"]:
            nat_id = nat["NatGatewayId"]
            if DRY_RUN:
                logger.info(f"  [DRY-RUN] Would delete NAT Gateway: {nat_id}")
            else:
                ec2.delete_nat_gateway(NatGatewayId=nat_id)
                logger.info(f"  ✅ Deleting NAT Gateway: {nat_id}")
                deleted.append(nat_id)
    except Exception as e:
        logger.error(f"  ❌ NAT Gateway error in {region}: {str(e)}")

    return deleted


def delete_eks_clusters(region):
    """Find and delete all EKS clusters (deletes node groups first)."""
    eks = boto3.client("eks", region_name=region)
    deleted = []

    try:
        clusters = eks.list_clusters()["clusters"]
        for cluster_name in clusters:
            # Must delete node groups before deleting the cluster
            try:
                nodegroups = eks.list_nodegroups(clusterName=cluster_name)["nodegroups"]
                for ng in nodegroups:
                    if DRY_RUN:
                        logger.info(f"  [DRY-RUN] Would delete EKS nodegroup: {ng}")
                    else:
                        eks.delete_nodegroup(clusterName=cluster_name, nodegroupName=ng)
                        logger.info(f"  ✅ Deleting EKS nodegroup: {ng}")
            except Exception as e:
                logger.warning(f"  ⚠️ Could not delete nodegroups for {cluster_name}: {str(e)}")

            if DRY_RUN:
                logger.info(f"  [DRY-RUN] Would delete EKS cluster: {cluster_name}")
            else:
                try:
                    eks.delete_cluster(name=cluster_name)
                    logger.info(f"  ✅ Deleting EKS cluster: {cluster_name}")
                    deleted.append(cluster_name)
                except Exception as e:
                    logger.warning(f"  ⚠️ EKS cluster {cluster_name} may need nodegroups to finish deleting first: {str(e)}")
    except Exception as e:
        logger.error(f"  ❌ EKS error in {region}: {str(e)}")

    return deleted


def release_elastic_ips(region):
    """Release all Elastic IPs ($3.60/month each when idle!)."""
    ec2 = boto3.client("ec2", region_name=region)
    released = []

    try:
        addresses = ec2.describe_addresses()["Addresses"]
        for addr in addresses:
            alloc_id = addr.get("AllocationId")
            public_ip = addr.get("PublicIp", "unknown")
            if alloc_id:
                if DRY_RUN:
                    logger.info(f"  [DRY-RUN] Would release EIP: {public_ip}")
                else:
                    # Disassociate first if attached
                    if "AssociationId" in addr:
                        try:
                            ec2.disassociate_address(AssociationId=addr["AssociationId"])
                        except Exception:
                            pass

                    ec2.release_address(AllocationId=alloc_id)
                    logger.info(f"  ✅ Released EIP: {public_ip}")
                    released.append(public_ip)
    except Exception as e:
        logger.error(f"  ❌ EIP error in {region}: {str(e)}")

    return released


def stop_sagemaker_notebooks(region):
    """Stop all running SageMaker notebook instances."""
    sm = boto3.client("sagemaker", region_name=region)
    stopped = []

    try:
        response = sm.list_notebook_instances(StatusEquals="InService")
        for nb in response["NotebookInstances"]:
            nb_name = nb["NotebookInstanceName"]
            if DRY_RUN:
                logger.info(f"  [DRY-RUN] Would stop SageMaker notebook: {nb_name}")
            else:
                sm.stop_notebook_instance(NotebookInstanceName=nb_name)
                logger.info(f"  ✅ Stopping SageMaker notebook: {nb_name}")
                stopped.append(nb_name)
    except Exception as e:
        logger.error(f"  ❌ SageMaker error in {region}: {str(e)}")

    return stopped


def delete_load_balancers(region):
    """Delete all Application/Network Load Balancers and Classic LBs."""
    deleted = []

    # ALB / NLB (v2)
    try:
        elbv2 = boto3.client("elbv2", region_name=region)
        lbs = elbv2.describe_load_balancers()["LoadBalancers"]
        for lb in lbs:
            lb_arn = lb["LoadBalancerArn"]
            lb_name = lb["LoadBalancerName"]
            if DRY_RUN:
                logger.info(f"  [DRY-RUN] Would delete ALB/NLB: {lb_name}")
            else:
                # Disable deletion protection
                try:
                    elbv2.modify_load_balancer_attributes(
                        LoadBalancerArn=lb_arn,
                        Attributes=[{"Key": "deletion_protection.enabled", "Value": "false"}]
                    )
                except Exception:
                    pass

                elbv2.delete_load_balancer(LoadBalancerArn=lb_arn)
                logger.info(f"  ✅ Deleted ALB/NLB: {lb_name}")
                deleted.append(lb_name)
    except Exception as e:
        logger.error(f"  ❌ ELBv2 error in {region}: {str(e)}")

    # Classic LB
    try:
        elb = boto3.client("elb", region_name=region)
        classic_lbs = elb.describe_load_balancers()["LoadBalancerDescriptions"]
        for clb in classic_lbs:
            clb_name = clb["LoadBalancerName"]
            if DRY_RUN:
                logger.info(f"  [DRY-RUN] Would delete Classic LB: {clb_name}")
            else:
                elb.delete_load_balancer(LoadBalancerName=clb_name)
                logger.info(f"  ✅ Deleted Classic LB: {clb_name}")
                deleted.append(clb_name)
    except Exception as e:
        logger.error(f"  ❌ Classic ELB error in {region}: {str(e)}")

    return deleted


def delete_unattached_ebs_volumes(region):
    """Delete all unattached (available) EBS volumes."""
    ec2 = boto3.client("ec2", region_name=region)
    deleted = []

    try:
        response = ec2.describe_volumes(
            Filters=[{"Name": "status", "Values": ["available"]}]
        )
        for vol in response["Volumes"]:
            vol_id = vol["VolumeId"]
            if DRY_RUN:
                logger.info(f"  [DRY-RUN] Would delete EBS volume: {vol_id}")
            else:
                ec2.delete_volume(VolumeId=vol_id)
                logger.info(f"  ✅ Deleted EBS volume: {vol_id}")
                deleted.append(vol_id)
    except Exception as e:
        logger.error(f"  ❌ EBS error in {region}: {str(e)}")

    return deleted


def lambda_handler(event, context):
    """
    Main entry point for the Lambda function.
    Triggered IMMEDIATELY by SNS when budget threshold is breached.
    This is the PRIMARY responder — fires before aws-nuke.
    """
    logger.info("=" * 60)
    logger.info("🚨 AWS NUCLEAR BUTTON ACTIVATED 🚨")
    logger.info(f"   Trigger event: {json.dumps(event, default=str)[:500]}")
    if DRY_RUN:
        logger.info("   ⚠️  DRY-RUN MODE — No resources will be deleted")
    logger.info("=" * 60)

    regions = get_all_regions()
    logger.info(f"Scanning {len(regions)} AWS regions (PRIMARY: {PRIMARY_REGION})...")

    # Track results
    results = {
        "ec2_terminated": [],
        "rds_deleted": [],
        "nat_gateways_deleted": [],
        "eks_clusters_deleted": [],
        "eips_released": [],
        "sagemaker_stopped": [],
        "load_balancers_deleted": [],
        "ebs_volumes_deleted": [],
    }

    for region in regions:
        logger.info(f"\n📍 Region: {region}")
        logger.info("-" * 40)

        results["ec2_terminated"].extend(terminate_ec2_instances(region))
        results["rds_deleted"].extend(delete_rds_instances(region))
        results["nat_gateways_deleted"].extend(delete_nat_gateways(region))
        results["eks_clusters_deleted"].extend(delete_eks_clusters(region))
        results["eips_released"].extend(release_elastic_ips(region))
        results["sagemaker_stopped"].extend(stop_sagemaker_notebooks(region))
        results["load_balancers_deleted"].extend(delete_load_balancers(region))
        results["ebs_volumes_deleted"].extend(delete_unattached_ebs_volumes(region))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TERMINATION REPORT")
    logger.info("=" * 60)
    total = 0
    for service, items in results.items():
        count = len(items)
        total += count
        logger.info(f"  {service}: {count} resources")
    logger.info(f"\n  TOTAL RESOURCES AFFECTED: {total}")
    logger.info("=" * 60)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Nuclear Button execution complete" + (" (DRY-RUN)" if DRY_RUN else ""),
            "total_resources_affected": total,
            "details": results
        }, default=str)
    }


# ---------- Local Testing ----------
if __name__ == "__main__":
    """Run locally for testing (outside Lambda)."""
    DRY_RUN = True  # ALWAYS dry-run when testing locally
    print("\n⚠️  Running in LOCAL TEST MODE with DRY_RUN=True\n")
    result = lambda_handler({"source": "local-test"}, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
