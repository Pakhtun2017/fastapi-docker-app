# Importing the logging module to record events and errors.
import logging

# Importing HTTPException from FastAPI to raise HTTP errors in a web context.
from fastapi import HTTPException # type: ignore

# Importing specific exceptions from botocore to handle AWS-related errors.
from botocore.exceptions import ClientError, NoCredentialsError

# Importing aioboto3 for asynchronous AWS SDK functionality.
import aioboto3  # type: ignore

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

async def create_security_group(
    ec2_client, 
    group_name: str, 
    group_description: str
) -> str:
    try:
        response = await ec2_client.create_security_group(
            GroupName=group_name, Description=group_description
        )
        group_id = response["GroupId"]
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
        response = await ec2_client.authorize_security_group_ingress(
                GroupId=group_id, 
                IpPermissions=ip_permissions
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

    