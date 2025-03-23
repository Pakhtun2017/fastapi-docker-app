# app/dependencies.py
import aioboto3 # type: ignore
from fastapi import Header, HTTPException, status # type: ignore

# Dependency using async context management.
async def get_ec2_client(
    profile: str | None = Header(default="default", description="AWS profile to use."),
    region: str | None = Header(default="us-east-1", description="AWS region to use.")
):
    try:
        session = aioboto3.Session(profile_name=profile, region_name=region)
        # client = await session.client("ec2") # you can't do it this way because it throws error indicating that the asynchronous client isn’t being properly awaited or managed
        # Use 'async with' to properly await client creation.
        async with session.client("ec2") as client:
            yield client  # Yield the client to the endpoint, and close when done. Umplemented with a generator that yields the client
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create EC2 client: {e}"
        )
