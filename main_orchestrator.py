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

import os
import yaml
from nornir_netmiko.tasks import netmiko_send_config, netmiko_send_command
from nornir_jinja2.plugins.tasks import template_file

def run_multi_vendor_deployment(task, extra_vars, job_id, stream_callback):
    """
    Core execution logic called per-host by Nornir's ThreadedRunner.
    Maps platform attributes, renders local Jinja2 templates, and deploys configs.
    """
    platform_driver_map = {
        "arista-eos": "arista_eos",
        "cisco-ios-xe": "cisco_ios",
        "cisco-nx-os": "cisco_nxos",
        "juniper-junos": "juniper_junos",
        "paloalto-panos": "paloalto_panos"
    }
    
    netbox_slug = task.host.platform
    target_driver = platform_driver_map.get(netbox_slug)
    
    if not target_driver:
        stream_callback(job_id, f"[{task.host.name}] ❌ Skipping: Unsupported platform slug '{netbox_slug}'")
        return f"Unsupported platform: {netbox_slug}"

    task.host.connection_options["netmiko"]["platform"] = target_driver
    stream_callback(task.host.name, f"Driver mapped to '{target_driver}'. Processing config templates...")

    # Load group configurations out of your local sharded workspace directory path context
    group_vars = {}
    yaml_path = os.path.join(os.path.dirname(__file__), "group_vars", "global.yaml")
    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as f:
            group_vars = yaml.safe_load(f) or {}

    merged_context = {**group_vars, **(extra_vars or {}), "host": task.host.dict()}

    template_name = f"{target_driver}.j2"
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    
    if not os.path.exists(os.path.join(template_dir, template_name)):
        stream_callback(task.host.name, f"⚠️ Warning: No matching template '{template_name}' found. Skipping.")
        return "Template missing"

    try:
        rendering = task.run(
            task=template_file,
            name="Render Vendor Template",
            template=template_name,
            path=template_dir,
            **merged_context
        )
        rendered_config = rendering.result.strip()
        stream_callback(task.host.name, "Jinja2 configuration payload rendered cleanly.")
    except Exception as te:
        stream_callback(task.host.name, f"❌ Jinja2 Generation Error: {str(te)}")
        raise te

    if not rendered_config:
        stream_callback(task.host.name, "🍃 Rendered configuration is empty. No execution required.")
        return "No changes"

    config_commands_list = [line.strip() for line in rendered_config.splitlines() if line.strip() and not line.startswith("#")]

    try:
        stream_callback(task.host.name, f"Pushing {len(config_commands_list)} generated configuration statements over SSH...")
        config_result = task.run(
            task=netmiko_send_config,
            name="Deploy Rendered Config",
            config_commands=config_commands_list
        )
        
        if target_driver in ["juniper_junos", "paloalto_panos"]:
            stream_callback(task.host.name, "Applying pending changes via explicit 'commit' operation...")
            task.run(task=netmiko_send_command, command_string="commit")

        stream_loop_lines = config_result.result.splitlines()
        for line in stream_loop_lines[-3:]:
            stream_callback(task.host.name, f" [Device Response] {line}")

        return "Successfully deployed configuration changes"

    except Exception as ee:
        stream_callback(task.host.name, f"❌ Netmiko SSH Execution Failure: {str(ee)}")
        raise ee
