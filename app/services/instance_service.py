import logging
from fastapi import HTTPException 
from botocore.exceptions import ClientError, NoCredentialsError
import aioboto3  
from .security_group_service import create_security_group, authorize_ingress, attach_security_group
from .key_pair_service import create_keypair
from app.config.config import FEATURE_SECURITY_GROUPS

# Configure logging for the integration test.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)


# Define an asynchronous function to create EC2 instances.
# The function takes an AWS EC2 client, an AMI ID, the minimum and maximum number of instances,
# a flag to indicate if a key pair should be created, and the key pair name.
async def create_instance(
    ec2_client, 
    ami_id: str, 
    min_count: int, 
    max_count: int, 
    create_key_pair: bool, 
    key_name: str,
    create_sg: bool,
    security_group_name: str,
    security_group_description: str,
    security_group_rules                          
) -> list[str]:
    try:
        # Log that the instance creation process is starting.
        logging.info("Initiating instance creation asynchronously.")

        # --- EC2 Instance Creation Block ---
        params = {
            "ImageId": ami_id,
            "MinCount": min_count or 1,
            "MaxCount": max_count or 1,
            "InstanceType": 't2.micro'
        }
        
        if FEATURE_SECURITY_GROUPS and create_sg:
            logging.info("Creating security group")
            group_id = await create_security_group(
                                ec2_client, 
                                security_group_name, 
                                security_group_description
            )
            ip_permissions = []
            for rule in security_group_rules:
                ip_ranges = [{"CidrIp": ip} for ip in rule.ip_ranges] if rule.ip_ranges else []
                ip_permission = {
                    "IpProtocol": rule.ip_protocol,
                    "FromPort": rule.from_port,
                    "ToPort": rule.to_port,
                    "IpRanges": ip_ranges,
                }
                ip_permissions.append(ip_permission)
            logging.info(f"Invoking authorize_ingress and passing these ip_permissions - {ip_permissions}")
            await authorize_ingress(
                ec2_client,
                group_id=group_id,
                ip_permissions=ip_permissions
            )
        
        # --- Key Pair Creation Block ---
        if create_key_pair:
            # IMPORTANT: Await the create_keypair utility function so it completes before proceeding.
            key_name = await create_keypair(ec2_client, key_name)
            params["KeyName"] = key_name
            
        # --- EC2 Instance Creation Block ---
        logging.info("Creating the EC2 instance")
        new_instances = await ec2_client.run_instances(**params)
        
        # Extract the instance IDs from the response.
        # Loop over the list of instances in the response.
        instance_ids = [instance.get('InstanceId') for instance in new_instances['Instances']]
        if FEATURE_SECURITY_GROUPS and create_sg:
            for instance_id in instance_ids:
                logging.info("Attaching security group to the instance")
                await attach_security_group(ec2_client, group_id=group_id, instance_id=instance_id)
        
        # Get a waiter object to check when the instances reach the 'running' state.
        waiter = ec2_client.get_waiter('instance_running')
        # Await the waiter until the specified instances are running.
        await waiter.wait(InstanceIds=instance_ids)
        
        # Log a success message with the list of created instance IDs.
        logging.info(f"Successfully created instances: {', '.join(instance_ids)}")
        # Return the list of instance IDs.
        return instance_ids

    # --- Error Handling ---
    except NoCredentialsError:
        logging.exception("Error: AWS credentials not found or are invalid.")
        raise HTTPException(status_code=400, detail="AWS credentials error")
    except ClientError:
        logging.exception("A client error occurred:")
        raise HTTPException(status_code=400, detail="AWS client error")
    except Exception as e:
        logging.exception("An unexpected error occurred:")
        raise HTTPException(status_code=500, detail="Unexpected error")


async def terminate_instance(ec2_client, instance_ids: list[str]) -> list[str]:
    try:
        logging.info(f"Initiating asynchronous termination for instances: {instance_ids}")
        # Terminate instances asynchronously using aioboto3
        await ec2_client.terminate_instances(InstanceIds=instance_ids)

        # Await the termination confirmation with aioboto3's waiter
        waiter = ec2_client.get_waiter('instance_terminated')
        await waiter.wait(InstanceIds=instance_ids)

        logging.info(f"Successfully terminated instances: {', '.join(instance_ids)}")

        return instance_ids  # Returning IDs directly (simple approach)

    except NoCredentialsError:
        logging.exception("AWS credentials are invalid or missing.")
        raise HTTPException(status_code=400, detail="AWS credentials error")

    except ClientError as e:
        logging.exception("AWS client error: %s", e)
        raise HTTPException(status_code=400, detail=f"AWS client error: {e}")

    except Exception as e:
        logging.exception("Unexpected error occurred: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected error")