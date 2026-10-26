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

import uuid
import zmq
import zmq.asyncio
from apscheduler.schedulers.asyncio import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from database import engine

data_store = SQLAlchemyDataStore(engine)
scheduler = AsyncScheduler(data_store)
ctx = zmq.asyncio.Context()
zmq_socket = ctx.socket(zmq.PUSH)

async def dispatch_scheduled_job(job_type: str, netbox_filters: dict, extra_vars: dict):
    try: zmq_socket.connect("tcp://127.0.0.1:5557")
    except zmq.ZMQError: pass
    job_id = f"cron-{str(uuid.uuid4())[:8]}"
    payload = {"job_id": job_id, "project_id": "global", "task": job_type, "netbox_filters": netbox_filters, "extra_vars": extra_vars}
    await zmq_socket.send_json(payload)

async def add_cron_schedule(name: str, cron_expr: str, job_type: str, filters: dict, extra_vars: dict):
    parts = cron_expr.split()
    if len(parts) != 5: raise ValueError("Invalid 5-field crontab pattern.")
    await scheduler.add_schedule(
        dispatch_scheduled_job, trigger='cron', id=name, name=name, args=[job_type, filters, extra_vars],
        minute=parts, hour=parts, day=parts, month=parts, day_of_week=parts, conflict_policy='replace'
    )
