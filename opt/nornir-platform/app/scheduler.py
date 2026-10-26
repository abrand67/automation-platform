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
    if not zmq_socket.closed:
        try:
            zmq_socket.connect("tcp://127.0.0.1:5555")
        except zmq.ZMQError:
            pass
            
    job_id = f"cron-{str(uuid.uuid4())[:8]}"
    payload = {
        "job_id": job_id,
        "task": job_type,
        "netbox_filters": netbox_filters,
        "extra_vars": extra_vars
    }
    await zmq_socket.send_json(payload)

async def add_cron_schedule(name: str, cron_expr: str, job_type: str, filters: dict, extra_vars: dict):
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError("Cron expression must contain exactly 5 standard fields.")
        
    await scheduler.add_schedule(
        dispatch_scheduled_job,
        trigger='cron',
        id=name,
        name=name,
        args=[job_type, filters, extra_vars],
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        conflict_policy='replace'
    )

