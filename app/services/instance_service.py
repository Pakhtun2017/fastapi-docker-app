# Importing the logging module to record events and errors.
import logging

# Importing HTTPException from FastAPI to raise HTTP errors in a web context.
from fastapi import HTTPException # type: ignore

# Importing specific exceptions from botocore to handle AWS-related errors.
from botocore.exceptions import ClientError, NoCredentialsError

# Importing aioboto3 for asynchronous AWS SDK functionality.
import aioboto3  # type: ignore


# Configure logging for the integration test.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Utility function to create a key pair if it doesn't already exist.
# This function is asynchronous because it awaits calls to the AWS API.
async def create_keypair(ec2_client, key_name):
    # Await the describe_key_pairs call to get existing key pairs.
    key_pairs_response = await ec2_client.describe_key_pairs()
    # Extract the key names from the returned list of key pair dictionaries.
    # The response is expected to have a "KeyPairs" key containing a list of dicts.
    existing_keys = [kp['KeyName'] for kp in key_pairs_response.get('KeyPairs', [])]
    
    # Check if the desired key pair does not already exist.
    if key_name not in existing_keys:
        # Create a new key pair if it doesn't exist.
        key_response = await ec2_client.create_key_pair(KeyName=key_name)
        # Extract the private key material from the response.
        key_material = key_response.get('KeyMaterial')
        # Save the private key to a file. This file operation is synchronous.
        filename = f"{key_name}.pem"
        with open(filename, "w") as key_file:
            key_file.write(key_material)
        # Change file permissions to read-only for security.
        import os
        os.chmod(filename, 0o400)
        # Return the key name as confirmation that it was created.
        return key_name
        # NOTE: The following logging statement will never be reached because it's after the return.
        logging.info(f"Created and saved key pair: {key_name}")
    else:
        # Log that the key pair already exists.
        logging.info(f"Key pair '{key_name}' already exists; reusing it.")
        # Consider returning the key_name here as well if needed.
        return key_name


# Define an asynchronous function to create EC2 instances.
# The function takes an AWS EC2 client, an AMI ID, the minimum and maximum number of instances,
# a flag to indicate if a key pair should be created, and the key pair name.
async def create_instance(ec2_client, ami_id: str, min_count: int, max_count: int, create_key_pair: bool, key_name: str) -> list[str]:
    try:
        # Log that the instance creation process is starting.
        logging.info("Initiating instance creation asynchronously.")

        # --- EC2 Instance Creation Block ---
        # When calling run_instances, AWS expects a dictionary without parameters that have None values.
        # Passing KeyName=None might cause AWS to reject the request.
        # Instead, only include KeyName if create_key_pair is True and key_name is a valid string.
        params = {
            "ImageId": ami_id,
            "MinCount": min_count or 1,
            "MaxCount": max_count or 1,
            "InstanceType": 't2.micro'
        }
        
        # --- Key Pair Creation Block ---
        if create_key_pair:
            # IMPORTANT: Await the create_keypair utility function so it completes before proceeding.
            key_name = await create_keypair(ec2_client, key_name)
            params["KeyName"] = key_name
            
        # --- EC2 Instance Creation Block ---
        # Call run_instances with the required parameters.
        # Note: AWS expects the parameter for the key pair to be 'KeyName' (capital K and N).
        new_instances = await ec2_client.run_instances(**params)
        
        # Extract the instance IDs from the response.
        # Loop over the list of instances in the response.
        instance_ids = [instance.get('InstanceId') for instance in new_instances['Instances']]
        
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