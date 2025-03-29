import logging
from fastapi import HTTPException 
from botocore.exceptions import ClientError, NoCredentialsError
import aioboto3 
import asyncio
import json

from typing import List

# Configure logging for the integration test.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

async def describe_instances_with_retry(ec2_client, instance_ids, max_attempts: int = 5, initial_delay: float = 1.0):
    """
    Attempts to call ec2_client.describe_instances with exponential backoff.
    :param ec2_client: The AWS EC2 client.
    :param instance_ids: List of instance IDs to describe.
    :param max_attempts: Maximum number of retry attempts.
    :param initial_delay: Initial delay in seconds before retrying.
    :return: The response from ec2_client.describe_instances.
    :raises Exception: If all attempts fail.
    """
    delay = initial_delay
    attempt = 0
    while attempt < max_attempts:
        try:
            response = await ec2_client.describe_instances(InstanceIds=instance_ids)
            # Optional: Validate the response structure to ensure data is present.
            if response.get('Reservations') and response['Reservations'][0].get('Instances'):
                return response
            else:
                # If the expected data is missing, raise an exception to trigger a retry.
                raise ValueError("Instance data not available yet")
        except Exception as e:
            attempt += 1
            logging.warning(f"Attempt {attempt} failed with error: {e}. Retrying in {delay} seconds...")
            if attempt >= max_attempts:
                logging.error("Maximum retry attempts reached. Giving up.")
                raise e
            await asyncio.sleep(delay)
            delay *= 2  # Exponential backoff: double the delay on each retry


async def create_security_group(
    ec2_client, 
    group_name: str, 
    group_description: str
) -> str:
    try:
        existing_sg_response = await ec2_client.describe_security_groups()
        # logging.info("Describe security groups response: %s", json.dumps(existing_sg_response, indent=2, default=str))
        existing_sg_names = [sg['GroupName'] for sg in existing_sg_response.get('SecurityGroups', [])]
        
        if group_name not in existing_sg_names:
            response = await ec2_client.create_security_group(
                GroupName=group_name, Description=group_description
            )
            group_id = response["GroupId"]
        else:
            logging.info(f"Security Group '{group_name}' already exists; reusing it.")
            group_id = next((sg['GroupId'] for sg in existing_sg_response["SecurityGroups"] if group_name == sg["GroupName"]), None)
        return group_id
    
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

    
async def authorize_ingress(
    ec2_client,
    group_id: str,
    ip_permissions: List[dict]
):
    try:
        existing_sg_response= await ec2_client.describe_security_groups()
        logging.info("Describe security groups response: %s", json.dumps(existing_sg_response, indent=2, default=str))
        existing_sg_id = [sg['GroupId'] for sg in existing_sg_response.get('SecurityGroups', [])]
        # First, find the security group dictionary that matches group_id.
        # Then compare that security group’s IpPermissions with your desired ip_permissions.
        existing_ip_permissions = next((sg['IpPermissions'] for sg in existing_sg_response['SecurityGroups'] if group_id == sg['GroupId']), None)
        if (group_id in existing_sg_id and ip_permissions not in existing_ip_permissions) or group_id not in existing_sg_id:
            authorized_ingress = await ec2_client.authorize_security_group_ingress(
                    GroupId=group_id, 
                    IpPermissions=ip_permissions
            )
        else: 
            logging.info(f"Group Id {group_id} is already authorized")
            authorized_ingress = next((sg['IpPermissions'] for sg in existing_sg_response['SecurityGroups'] if group_id == sg['GroupId']), None)
        existing_sg_response= await ec2_client.describe_security_groups()
        logging.info("Describe authorized_ingress response: %s", json.dumps(existing_sg_response, indent=2, default=str))
        return authorized_ingress
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

async def attach_security_group(
    ec2_client,
    group_id: str,
    instance_id: str
):
    try:
        # Retrieve current security groups for the instance
        # response = await ec2_client.describe_instances(InstanceIds=[instance_id])
        response = await describe_instances_with_retry(ec2_client, [instance_id])
        # logging.info("Describe security groups response: %s", json.dumps(response, indent=2, default=str))
        instance = response['Reservations'][0]['Instances'][0]
        current_sg_ids = [sg['GroupId'] for sg in instance['SecurityGroups']]
        
        if group_id not in current_sg_ids:
            current_sg_ids.append(group_id)
        response = await ec2_client.modify_instance_attribute(
            InstanceId=instance_id,
            Groups=current_sg_ids           
        )
        return response
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
    
    