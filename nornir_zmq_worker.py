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
load_dotenv()  # Ingest environment profile mappings into system memory immediately on boot

import os
import sys
import asyncio
import json
import hvac
import zmq
import zmq.asyncio
from redis import Redis
from nornir import InitNornir

# Conditional safety load for backend Nornir inventory plugin tools
try:
    from nornir_netbox.plugins.inventory import NetboxInventory2
except ImportError:
    pass

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
    if not client.is_authenticated(): 
        raise Exception("Vault authentication failed.")
    read_response = client.secrets.kv.v2.read_secret_version(path=secret_path)
    return read_response['data']['data']

def execute_nornir_task(task_name: str, netbox_filters: dict, extra_vars: dict, job_id: str, project_id: str):
    historical_raw_logs = []
    stream_log(job_id, f"[Fluxara Engine] Task initialization engaged for project path tracking: {project_id}", historical_raw_logs)
    
    # Direct path routing targeting your explicit 'Fluxara' GitLab workspace root
    workspace_path = "/opt/Fluxara/workspaces/Fluxara"
    
    if os.path.exists(workspace_path):
        stream_log(job_id, f"[Source Control] Directing runtime modules search query path to: {workspace_path}", historical_raw_logs)
        sys.path.insert(0, workspace_path)

    try:
        # Dynamically load your multi-vendor execution engine checked out of GitLab
        from main_orchestrator import run_multi_vendor_deployment
    except ImportError as ie:
        stream_log(job_id, f"CRITICAL: Failed to import main_orchestrator.py from GitLab directory: {str(ie)}", historical_raw_logs)
        if workspace_path in sys.path: 
            sys.path.remove(workspace_path)
        return

    try:
        # Initialize dynamic NetBox inventory parameters securely from system environment profiles
        nr = InitNornir(
            runner={"plugin": "threaded", "options": {"num_workers": 25}},
            inventory={
                "plugin": "NetboxInventory2", 
                "options": {
                    "nb_url": os.getenv("NETBOX_URL"), 
                    "nb_token": os.getenv("NETBOX_TOKEN"), 
                    "ssl_verify": True, 
                    "filter_parameters": netbox_filters
                }
            }
        )
    except Exception as e:
        stream_log(job_id, f"CRITICAL: NetBox Inventory load failure: {str(e)}", historical_raw_logs)
        if workspace_path in sys.path: 
            sys.path.remove(workspace_path)
        return

    if not nr.inventory.hosts:
        stream_log(job_id, "WARNING: No hosts resolved for given NetBox criteria filters.", historical_raw_logs)
        if workspace_path in sys.path: 
            sys.path.remove(workspace_path)
        return

    # Invoke your custom multi-vendor execution script compiled inside GitLab
    try:
        results = nr.run(
            task=run_multi_vendor_deployment,
            name=task_name,
            extra_vars=extra_vars,
            job_id=job_id,
            stream_callback=lambda host, msg: stream_log(job_id, f"[{host}] {msg}", historical_raw_logs)
        )
    except Exception as run_err:
        stream_log(job_id, f"CRITICAL: Execution failure inside Nornir run loop: {str(run_err)}", historical_raw_logs)
        results = None

    # Clean up environmental thread modules searching paths post-execution
    if workspace_path in sys.path: 
        sys.path.remove(workspace_path)

    if results:
        stream_log(job_id, "Archiving logging matrices data metrics to PostgreSQL...", historical_raw_logs)
        asyncio.run(archive_job_run(job_id, results, historical_raw_logs))

async def start_worker_loop(shard_endpoint: str):
    ctx = zmq.asyncio.Context()
    socket = ctx.socket(zmq.PULL)
    socket.connect(shard_endpoint)
    print(f"[System] Fluxara worker sharded loop process bound to target channel: {shard_endpoint}", flush=True)
    
    while True:
        job_payload = await socket.recv_json()
        await asyncio.to_thread(
            execute_nornir_task, 
            job_payload.get("task"), 
            job_payload.get("netbox_filters", {}), 
            job_payload.get("extra_vars", {}), 
            job_payload.get("job_id"),
            job_payload.get("project_id", "Fluxara")
        )

if __name__ == "__main__":
    if len(sys.argv) < 2: 
        sys.exit("[CRITICAL] Missing target endpoint string channel argument parameter mapping.")
    # Read endpoint flag array on execution init
    target_endpoint = sys.argv[1]
    asyncio.run(start_worker_loop(target_endpoint))
