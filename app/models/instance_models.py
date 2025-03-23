from pydantic import BaseModel # type: ignore

# Pydantic model for the incoming request body.
# It defines the expected JSON structure (fields, defaults, and types).
class InstanceRequest(BaseModel):
    ami_id: str = 'ami-02a53b0d62d37a757'
    min_count: int = 1
    max_count: int = 1

# Pydantic model for the response.
# This model will be used to validate and document the JSON response.
class InstanceResponse(BaseModel):
    instance_ids: list[str]
    status: str

class TerminateRequest(BaseModel):
    instance_ids: list[str]