import logging
from fastapi import HTTPException 
from botocore.exceptions import ClientError, NoCredentialsError
import aioboto3 

# Configure logging for the integration test.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(filename)s:%(funcName)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

async def create_keypair(ec2_client, key_name):

    # Extract the key names from the returned list of key pair dictionaries.
    # The response is expected to have a "KeyPairs" key containing a list of dicts.
    key_pairs_response = await ec2_client.describe_key_pairs()
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

