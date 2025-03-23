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


# Define an asynchronous function to create EC2 instances.
# The function takes an AWS EC2 client, an AMI ID, and the minimum and maximum number of instances to create.
async def create_instance(ec2_client, ami_id: str, min_count: int, max_count: int) -> list[str]:
    try:
        # Log the start of the instance creation process.
        logging.info("Initiating instance creation asynchronously.")
        
        # Asynchronously call the AWS EC2 run_instances method using 'await'
        # This sends a request to launch new EC2 instances with the specified parameters.
        new_instances = await ec2_client.run_instances(
            ImageId=ami_id,                    # The Amazon Machine Image (AMI) ID for the instance.
            MinCount=min_count or 1,           # Minimum number of instances to launch (default to 1 if not provided).
            MaxCount=max_count or 1,           # Maximum number of instances to launch (default to 1 if not provided).
            InstanceType='t2.micro'            # Instance type, here a small, low-cost option is used.
        )
        
        # Extract the instance IDs from the response.
        # This list comprehension loops through each instance in the returned data.
        instance_ids = [instance.get('InstanceId') for instance in new_instances['Instances']]
        
        # Get a waiter object that helps wait for the instances to reach the 'running' state.
        # Waiters abstract the polling process until the condition is met.
        waiter = ec2_client.get_waiter('instance_running')
        
        # Asynchronously wait until all instances are running.
        # The waiter will poll AWS until the specified instances are in the 'running' state.
        await waiter.wait(InstanceIds=instance_ids)
        
        # Log a success message with the list of created instance IDs.
        logging.info(f"Successfully created instances: {', '.join(instance_ids)}")
        
        # Return the list of instance IDs as confirmation.
        return instance_ids

    # Catch exception when AWS credentials are not found or invalid.
    except NoCredentialsError:
        logging.exception("Error: AWS credentials not found or are invalid.")
        raise HTTPException(status_code=400, detail="AWS credentials error")
    
    # Catch general client errors from AWS operations.
    except ClientError:
        logging.exception("A client error occurred:")
        raise HTTPException(status_code=400, detail="AWS client error")
    # Catch any other unexpected exceptions.
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