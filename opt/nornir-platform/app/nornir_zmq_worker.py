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

valkey_client = Redis(host=os.getenv("VALKEY_HOST", "127.0.0.1"), port=6379, db=0)

def stream_log(job_id: str, message: str, persistent_log_list: list):
    persistent_log_list.append(message)
    channel_name = f"logs:job:{job_id}"
    valkey_client.publish(channel_name, json.dumps({"message": message}))

def get_vault_credentials(secret_path: str, job_id: str, log_list: list) -> dict:
    client = hvac.Client(url=os.getenv("VAULT_ADDR", "http://127.0.0.1:8200"))
    client.token = os.getenv("VAULT_TOKEN")
    if not client.is_authenticated():
        raise Exception("Vault configuration credentials rejected.")
    read_response = client.secrets.kv.v2.read_secret_version(path=secret_path)
    return read_response['data']['data']

def execute_nornir_task(task_name: str, netbox_filters: dict, extra_vars: dict, job_id: str):
    historical_raw_logs = []
    stream_log(job_id, "Pulling active fleet inventories dynamically from NetBox...", historical_raw_logs)
    
    try:
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
        stream_log(job_id, f"CRITICAL: NetBox synchronization failed: {str(e)}", historical_raw_logs)
        return

    if not nr.inventory.hosts:
        stream_log(job_id, "WARNING: Zero switches matched specific inventory tags.", historical_raw_logs)
        return

    try:
        credentials = get_vault_credentials("network/credentials", job_id, historical_raw_logs)
        stream_log(job_id, "Dynamic SSH keys pulled from Vault successfully.", historical_raw_logs)
    except Exception:
        return

    def netmiko_execution_engine(task):
        platform_mapping = {"arista-eos": "arista_eos", "cisco-ios-xe": "cisco_ios", "juniper-junos": "juniper_junos"}
        task.host.connection_options["netmiko"] = {
            "platform": platform_mapping.get(task.host.platform, "cisco_ios"),
            "extras": {
                "username": credentials.get("username"),
                "password": credentials.get("password"),
                "secret": credentials.get("enable_secret", ""),
                "ssh_strict": False, "fast_cli": True
            }
        }
        
        commands = extra_vars.get("commands", [])
        configs = extra_vars.get("configs", [])
        output_log = []

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
        if host_result.failed:
            stream_log(job_id, f"[{host}] ❌ RUN TIME FAILED:\n{host_result.exception}", historical_raw_logs)
        else:
            stream_log(job_id, f"[{host}] ✅ ENGINE EXECUTION SUCCESS", historical_raw_logs)

    stream_log(job_id, "Archiving logging aggregates to PostgreSQL databases...", historical_raw_logs)
    asyncio.run(archive_job_run(job_id, results, historical_raw_logs))

async def start_worker_loop():
    ctx = zmq.asyncio.Context()
    socket = ctx.socket(zmq.PULL)
    socket.connect("tcp://127.0.0.1:5555")
    
    while True:
        job_payload = await socket.recv_json()
        await asyncio.to_thread(
            execute_nornir_task, 
            job_payload.get("task"), 
            job_payload.get("netbox_filters", {}), 
            job_payload.get("extra_vars", {}), 
            job_payload.get("job_id")
        )

if __name__ == "__main__":
    asyncio.run(start_worker_loop())

