# Copyright 2026 Allan Brand
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://apache.org
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific permissions and
# limitations under the License.

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal
from enum import Enum

class SupportedVendors(str, Enum):
    """
    Explicitly tracks the NetBox platform slugs supported natively 
    by the Fluxara multi-vendor automation framework.
    """
    ARISTA_EOS = "arista-eos"
    CISCO_IOS_XE = "cisco-ios-xe"
    CISCO_NX_OS = "cisco-nx-os"
    JUNIPER_JUNOS = "juniper-junos"
    PALOALTO_PANOS = "paloalto-panos"
    LINUX_SERVER = "linux-server"
    NVIDIA_MELLANOX = "nvidia-mellanox"
    CUMULUS_LINUX = "cumulus-linux"

class AutomationJobRequest(BaseModel):
    job_type: str = Field(
        ..., 
        description="The name of the Nornir script or execution playbook module to evaluate"
    )
    
    netbox_filters: Dict[str, Any] = Field(
        ..., 
        description="Dynamic filtering arguments passed straight to NetBox (e.g. site, role, platform, status)",
        examples=[{"site": "dfw", "role": "backbone-switch", "platform": "cisco-nx-os"}]
    )
    
    extra_vars: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Optional operational parameter arrays like custom configurations or verification checks"
    )

    class Config:
        """Enforces ORM attributes integration parameters and strict type mapping."""
        use_enum_values = True
        populate_by_name = True
