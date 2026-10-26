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

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import asyncio
import json
import hvac
import zmq
import zmq.asyncio
from redis import Redis
from nornir import InitNornir
from nornir_netbox.plugins.inventory import NetboxInventory2
from nornir_netmiko.tasks import netmiko_send_command, netmiko_send_config
from tasks import archive_job_run

VALKEY_HOST = os.getenv("VALKEY_HOST", "127.0.0.1")
valkey_client = Redis(host=VALKEY_HOST, port=6379, db=0)

def stream_log(job_id: str, message: str, persistent_log_list: list):
    persistent_log_list.append(message)
    channel_name = f"logs:job:{job_id}"
    valkey_client.publish(channel_name, json.dumps({"message": message}))

def get_vault_credentials(secret_path: str, job_id: str, log_list: list) -> dict:
    client = hvac.Client(url=os.getenv("VAULT_ADDR", "http://127.0.0.1:8200"))
    client.token = os.getenv("VAULT_TOKEN")
    if not client.is_authenticated(): raise Exception("Vault authentication failed.")
    read_response = client.secrets.kv.v2.read_secret_version(path=secret_path)
    return read_response['data']['data']

def execute_nornir_task(task_name: str, netbox_filters: dict, extra_vars: dict, job_id: str, project_id: str):
    historical_raw_logs = []
    stream_log(job_id, f"[Shard Engine] Task initialization engaged for project: {project_id}", historical_raw_logs)
    
    workspace_path = f"/opt/Fluxara/workspaces/project_{project_id}" if project_id != "global" else None
    if workspace_path and os.path.exists(workspace_path):
        sys.path.insert(0, workspace_path)

    try:
        nr = InitNornir(
            runner={"plugin": "threaded", "options": {"num_workers": 25}},
            inventory={"plugin": "NetboxInventory2", "options": {"nb_url": os.getenv("NETBOX_URL"), "nb_token": os.getenv("NETBOX_TOKEN"), "ssl_verify": True, "filter_parameters": netbox_filters}}
        )
    except Exception as e:
        stream_log(job_id, f"CRITICAL: Inventory load failure: {str(e)}", historical_raw_logs)
        return

    if not nr.inventory.hosts:
        stream_log(job_id, "WARNING: No hosts resolved for given NetBox criteria filters.", historical_raw_logs)
        return

    try: credentials = get_vault_credentials("network/credentials", job_id, historical_raw_logs)
    except Exception: return

    def netmiko_execution_engine(task):
        platform_mapping = {"arista-eos": "arista_eos", "cisco-ios-xe": "cisco_ios", "juniper-junos": "juniper_junos"}
        task.host.connection_options["netmiko"] = {
            "platform": platform_mapping.get(task.host.platform, "cisco_ios"),
            "extras": {"username": credentials.get("username"), "password": credentials.get("password"), "secret": credentials.get("enable_secret", ""), "ssh_strict": False, "fast_cli": True}
        }
        commands, configs, output_log = extra_vars.get("commands", []), extra_vars.get("configs", []), []
        if commands:
            for cmd in commands:
                res = task.run(task=netmiko_send_command, command_string=cmd)
                output_log.append(f"Command:\n{res.result}")
        elif configs:
            res = task.run(task=netmiko_send_config, config_commands=configs)
            output_log.append(f"Config Modified:\n{res.result}")
        return "\n".join(output_log)

    results = nr.run(task=netmiko_execution_engine, name=task_name)

    for host, host_result in results.items():
        if host_result.failed: stream_log(job_id, f"[{host}] ❌ EXECUTION PATH FAILURE:\n{host_result.exception}", historical_raw_logs)
        else: stream_log(job_id, f"[{host}] ✅ EXECUTION COMPLETED CLEANLY", historical_raw_logs)

    if workspace_path and workspace_path in sys.path: sys.path.remove(workspace_path)
    stream_log(job_id, "Archiving logging matrices data to PostgreSQL...", historical_raw_logs)
    asyncio.run(archive_job_run(job_id, results, historical_raw_logs))

async def start_worker_loop(shard_endpoint: str):
    ctx = zmq.asyncio.Context()
    socket = ctx.socket(zmq.PULL)
    socket.connect(shard_endpoint)
    print(f"[System] Worker sharded loop process bound to target channel: {shard_endpoint}", flush=True)
    while True:
        job_payload = await socket.recv_json()
        await asyncio.to_thread(
            execute_nornir_task, job_payload.get("task"), job_payload.get("netbox_filters", {}), job_payload.get("extra_vars", {}), job_payload.get("job_id"), job_payload.get("project_id", "global")
        )

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit("[CRITICAL] Missing target endpoint string channel argument parameter mapping.")
    asyncio.run(start_worker_loop(sys.argv))
