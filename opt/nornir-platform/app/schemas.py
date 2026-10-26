from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class AutomationJobRequest(BaseModel):
    job_type: str = Field(..., description="The name of the Nornir script or execution playbook to run")
    netbox_filters: Dict[str, Any] = Field(
        ..., 
        description="Dynamic filtering arguments passed straight to NetBox (e.g. site, role, status)",
        examples=[{"site": "dfw", "role": "backbone-switch"}]
    )
    extra_vars: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Optional execution arrays like configuration commands or operational checks"
    )

