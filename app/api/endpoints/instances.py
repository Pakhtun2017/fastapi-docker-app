from fastapi import APIRouter, Depends 
from app.models.instance_models import InstanceRequest, InstanceResponse, TerminateRequest
from app.services import instance_service
from app.dependencies import get_ec2_client
import logging
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

# Create a router instance. Routers allow you to group endpoints together.
router = APIRouter()

# Define an async POST endpoint for creating EC2 instances.
@router.post("/create-instance", response_model=InstanceResponse)
async def api_create_instance(
    instance_req: InstanceRequest,        # FastAPI parses the JSON body into this Pydantic model.
    ec2_client = Depends(get_ec2_client)    # FastAPI injects the EC2 client via the dependency.
):
    # Await the asynchronous service call.
    instance_ids = await instance_service.create_instance(
        ec2_client,
        instance_req.ami_id,
        instance_req.min_count,
        instance_req.max_count,
        instance_req.create_key_pair,
        instance_req.key_name,
        instance_req.create_security_group,
        instance_req.security_group_name,
        instance_req.security_group_description,
        instance_req.security_group_rules
    )
    # Return the response data conforming to the InstanceResponse model.
    return InstanceResponse(instance_ids=instance_ids, status="running")

# Define an async POST endpoint for terminating EC2 instances.
@router.delete("/terminate-instance", response_model=InstanceResponse)
async def api_terminate_instance(
    terminate_req: TerminateRequest,
    ec2_client = Depends(get_ec2_client)
):
    # Call your async terminate service
    terminated_instance_ids = await instance_service.terminate_instance(
        ec2_client,
        terminate_req.instance_ids
    )

    # Return the correct status after termination initiation
    return InstanceResponse(instance_ids=terminated_instance_ids, status="terminated")
