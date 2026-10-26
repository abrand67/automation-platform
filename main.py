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

import uuid
import json
import os
import asyncio
import zmq
import zmq.asyncio
import httpx
import redis.asyncio as aioredis
from datetime import timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from schemas import AutomationJobRequest
from database import get_db_session, JobExecution, User, ActivityStream
from security import (
    RoleChecker, 
    verify_password, 
    create_access_token, 
    get_current_user, 
    get_ws_current_user,
    ObjectPermissionGuard
)
from scheduler import scheduler, add_cron_schedule
from auth_providers import authenticate_via_active_directory, authenticate_via_radius
from git_manager import sync_gitlab_project

app = FastAPI(title="Fluxara Enterprise Automation Engine")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

VALKEY_HOST = os.getenv("VALKEY_HOST", "127.0.0.1")
VALKEY_URL = f"redis://{VALKEY_HOST}:6379/0"

zmq_context = zmq.asyncio.Context()
zmq_shards = {}
allow_operators = RoleChecker(["admin", "operator"])

@app.on_event("startup")
async def startup_event():
    """Initializes localized, sharded ZeroMQ routing sockets and boots background timers."""
    global zmq_shards
    shard_topologies = {
        "dfw": "tcp://127.0.0.1:5555",
        "aus": "tcp://127.0.0.1:5556",
        "global": "tcp://127.0.0.1:5557"
    }
    for region, endpoint in shard_topologies.items():
        sock = zmq_context.socket(zmq.PUSH)
        sock.bind(endpoint) if "127.0.0.1" in endpoint else sock.connect(endpoint)
        zmq_shards[region] = sock
    await scheduler.start_in_background()

@app.get("/login", response_class=HTMLResponse)
async def get_login_gateway_page(request: Request):
    """Serves the unauthenticated centralized user interface login card wrapper."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def get_job_dashboard(request: Request, job_id: str):
    """Serves the main single-page tabbed dashboard shell viewport mapping."""
    return templates.TemplateResponse("dashboard.html", {"request": request, "job_id": job_id})

@app.post("/api/v1/auth/token", response_model=dict)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db_session)
):
    """Processes centralized authentication fallback loops across enterprise directories."""
    auth_success = False
    user_role = "viewer"
    username = form_data.username
    password = form_data.password

    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalars().first()

    if user and verify_password(password, user.hashed_password):
        if not user.is_active: 
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account disabled.")
        auth_success = True
        user_role = user.role
    else:
        if authenticate_via_active_directory(username, password): 
            auth_success = True
            user_role = "operator"
        elif authenticate_via_radius(username, password): 
            auth_success = True
            user_role = "operator"

    if not auth_success: 
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Authentication failed across all directory providers.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token_expires = timedelta(minutes=120)
    access_token = create_access_token(
        data={"sub": username, "role": user_role}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user_role}

@app.post("/api/v1/projects/{project_id}/sync", status_code=status.HTTP_200_OK)
async def trigger_gitlab_project_sync(
    project_id: str, 
    repo_url: str, 
    branch: str = "main", 
    gitlab_token: Optional[str] = None, 
    db: AsyncSession = Depends(get_db_session), 
    current_user: User = Depends(get_current_user), 
    has_clearance: bool = Depends(ObjectPermissionGuard(object_type="project", action="write"))
):
    """Manual code synchronization pipeline pulling repo elements onto server paths."""
    audit_log = ActivityStream(
        id=str(uuid.uuid4()), actor_username=current_user.username, action="UPDATE", 
        object_type="project_git_sync", object_id=project_id, 
        changes_json={"repo_url": repo_url, "branch": branch}
    )
    db.add(audit_log)
    await db.commit()
    try:
        loop = asyncio.get_event_loop()
        project_path = await loop.run_in_executor(None, sync_gitlab_project, project_id, repo_url, branch, gitlab_token)
        return {"status": "SUCCESS", "project_id": project_id, "synchronized_path": project_path}
    except Exception as e: 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/v1/webhook/gitlab", status_code=status.HTTP_200_OK)
async def gitlab_webhook_receiver(
    request: Request,
    x_gitlab_token: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session)
):
    """Automated webhook endpoint triggered instantly by GitLab push events."""
    secret_webhook_token = os.getenv("GITLAB_WEBHOOK_SECRET", "SuperSecretWebhookKey123!!!")
    if x_gitlab_token != secret_webhook_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="GitLab signature token verification failed.")

    payload = await request.json()
    ref_branch = payload.get("ref", "")
    
    if "refs/heads/main" in ref_branch:
        repo_url = payload.get("project", {}).get("git_http_url")
        user_name = payload.get("user_name", "GitLab Webhook")
        
        audit_log = ActivityStream(
            id=str(uuid.uuid4()), actor_username=f"git:{user_name.lower().replace(' ', '_')}", action="UPDATE",
            object_type="webhook_sync", object_id="Fluxara",
            changes_json={"branch": ref_branch, "commit": payload.get("after")}
        )
        db.add(audit_log)
        await db.commit()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, sync_gitlab_project, "Fluxara", repo_url, "main", None)
        return {"status": "SUCCESS", "detail": "Fluxara workspace updated synchronously."}

    return {"status": "IGNORED", "detail": "Push event occurred outside of target tracking branch bounds."}

verify_project_execution = ObjectPermissionGuard(object_type="project", action="execute")

@app.post("/api/v1/projects/{project_id}/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_source_controlled_job(
    project_id: str, 
    payload: AutomationJobRequest, 
    db: AsyncSession = Depends(get_db_session), 
    current_user: User = Depends(get_current_user), 
    has_clearance: bool = Depends(verify_project_execution)
):
    """Validates object clearances, appends compliance audit rows, and routes across site shards."""
    job_id = str(uuid.uuid4())
    target_site = payload.netbox_filters.get("site", "global")
    target_socket = zmq_shards.get(target_site, zmq_shards["global"])

    audit_log = ActivityStream(
        id=str(uuid.uuid4()), actor_username=current_user.username, action="EXECUTE", 
        object_type="project_task", object_id=project_id, 
        changes_json={"job_id": job_id, "target_shard": target_site, "task_type": payload.job_type, "filters": payload.netbox_filters}
    )
    db.add(audit_log)
    new_job = JobExecution(id=job_id, job_type=payload.job_type, status="DISPATCHED", filters=payload.netbox_filters)
    db.add(new_job)
    await db.commit()
    
    job_message = {"job_id": job_id, "project_id": project_id, "task": payload.job_type, "netbox_filters": payload.netbox_filters, "extra_vars": payload.extra_vars}
    await target_socket.send_json(job_message)
    return {"job_id": job_id, "status": "DISPATCHED", "routed_shard": target_site}

@app.get("/scheduler", response_class=HTMLResponse)
async def list_schedules_pane(request: Request):
    schedules = await scheduler.get_schedules()
    return templates.TemplateResponse("scheduler_pane.html", {"request": request, "schedules": schedules})

@app.post("/scheduler/add", response_class=HTMLResponse)
async def create_new_schedule(request: Request, name: str = Form(...), cron_expr: str = Form(...), job_type: str = Form(...), site_filter: str = Form(...)):
    filters = {"site": site_filter, "status": "active"}
    await add_cron_schedule(name, cron_expr, job_type, filters, extra_vars={"commands": ["show version"]})
    schedules = await scheduler.get_schedules()
    return templates.TemplateResponse("scheduler_pane.html", {"request": request, "schedules": schedules})

@app.delete("/scheduler/delete/{schedule_id}", response_class=HTMLResponse)
async def delete_active_schedule(request: Request, schedule_id: str):
    await scheduler.remove_schedule(schedule_id)
    schedules = await scheduler.get_schedules()
    return templates.TemplateResponse("scheduler_pane.html", {"request": request, "schedules": schedules})

@app.get("/inventories", response_class=HTMLResponse)
async def list_inventories_component_pane(request: Request):
    return templates.TemplateResponse("inventories_pane.html", {"request": request})

@app.get("/projects", response_class=HTMLResponse)
async def list_projects_component_pane(request: Request):
    return templates.TemplateResponse("projects_pane.html", {"request": request})

@app.get("/projects/{project_id}/audit", response_class=HTMLResponse)
async def get_project_audit_pane(project_id: str, db: AsyncSession = Depends(get_db_session)):
    query = select(ActivityStream).filter(ActivityStream.object_id == project_id).order_by(ActivityStream.timestamp.desc()).limit(10)
    result = await db.execute(query)
    logs = result.scalars().all()
    if not logs: 
        return '<div style="color:var(--text-muted); font-style:italic; padding:1rem; font-size:0.75rem;">No historical audit events logged.</div>'
    html_rows = "".join([f'<tr style="border-bottom:1px solid #1e293b;"><td style="padding:0.5rem; color:var(--text-main); font-weight:600;">{l.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</td><td style="padding:0.5rem; color:var(--emerald-green);">{l.actor_username}</td><td style="padding:0.5rem;">{l.action}</td><td style="padding:0.5rem; color:var(--text-muted);">{l.changes_json.get("task_type", "N/A") if l.changes_json else "N/A"}</td></tr>' for l in logs])
    return f'<div style="background-color:#000; border:1px solid #1e293b; border-radius:4px; padding:1rem; margin-top:0.5rem;"><table style="width:100%; font-family:monospace; font-size:0.7rem; border-collapse:collapse; text-align:left;"><thead><tr style="color:var(--text-muted); border-bottom:1px solid var(--border-color);"><th style="padding:0.5rem;">Timestamp (UTC)</th><th style="padding:0.5rem;">Actor</th><th style="padding:0.5rem;">Action</th><th style="padding:0.5rem;">Context</th></tr></thead><tbody>{html_rows}</tbody></table></div>'

@app.get("/inventories/{site_slug}/devices", response_class=HTMLResponse)
async def get_site_devices_component(site_slug: str, current_user: User = Depends(get_current_user)):
    nb_url = os.getenv("NETBOX_URL", "https://netbox.local").rstrip("/")
    nb_token = os.getenv("NETBOX_TOKEN", "your_token_here")
    headers = {"Authorization": f"Token {nb_token}", "Accept": "application/json"}
    html_rows = ""
    try:
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(f"{nb_url}/api/dcim/devices/?site={site_slug}&status=active", headers=headers, timeout=5.0)
            if response.status_code != 200: raise Exception("NetBox fetch error")
            devices = response.json().get("results",)
        if not devices: 
            return '<div style="color:var(--text-muted); font-style:italic; padding:1rem; font-size:0.75rem;">No hosts active.</div>'
        for dev in devices:
            p_obj = dev.get("platform")
            m_p = p_obj.get("name") if p_obj else "Unknown"
            ip_obj = dev.get("primary_ip") or dev.get("primary_ip4")
            m_ip = ip_obj.get("address", "Unassigned").split("/") if ip_obj else "No IP"
            html_rows += f'<tr style="border-bottom:1px solid #1e293b;"><td style="padding:0.5rem; color:var(--text-main); font-weight:600;">{dev.get("name") or "Unnamed"}</td><td style="padding:0.5rem; color:var(--text-muted);">{m_p}</td><td style="padding:0.5rem; font-family:monospace; color:var(--amber-orange);">{m_ip}</td><td style="padding:0.5rem;"><span style="color:var(--emerald-green);">● {dev.get("status", {}).get("label", "Active")}</span></td></tr>'
    except Exception as e: 
        return f'<div style="color:var(--rose-red); font-family:monospace; font-size:0.75rem; padding:0.75rem;">[CRITICAL] Error: {str(e)}</div>'
    return f'<div style="background-color:#000; border:1px solid #1e293b; border-radius:4px; padding:1rem; margin-top:0.5rem;"><table style="width:100%; font-family:monospace; font-size:0.7rem; border-collapse:collapse; text-align:left;"><thead><tr style="color:var(--text-muted); border-bottom:1px solid var(--border-color);"><th style="padding:0.5rem;">Device Hostname</th><th style="padding:0.5rem;">Hardware Model</th><th style="padding:0.5rem;">Management IP</th><th style="padding:0.5rem;">Status</th></tr></thead><tbody>{html_rows}</tbody></table></div>'

@app.websocket("/ws/v1/jobs/{job_id}/logs")
async def stream_job_logs(websocket: WebSocket, job_id: str, db: AsyncSession = Depends(get_db_session)):
    await websocket.accept()
    token_str = websocket.query_params.get("token")
    user = await get_ws_current_user(token=token_str, db=db) if token_str else None
    if not user:
        await websocket.send_text('<div id="terminal-log-output" hx-swap-oob="beforeend"><div class="text-rose-400 font-semibold">[Security] Refused.</div></div>')
        await websocket.close(code=1008)
        return
    valkey = aioredis.from_url(VALKEY_URL, decode_responses=True)
    pubsub = valkey.pubsub()
    await pubsub.subscribe(f"logs:job:{job_id}")
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                raw_text = json.loads(message["data"]).get("message", "")
                color_class = "text-slate-300"
                if "❌" in raw_text or "CRITICAL" in raw_text: color_class = "text-rose-400 font-semibold"
                elif "✅" in raw_text: color_class = "text-emerald-400 font-semibold"
                await websocket.send_text(f'<div id="terminal-log-output" hx-swap-oob="beforeend"><div class="{color_class} text-xs"><span class="text-slate-600 mr-2">&gt;&gt;&gt;</span>{raw_text}</div></div>')
            await asyncio.sleep(0.01)
    except WebSocketDisconnect: pass
    finally:
        await pubsub.unsubscribe(f"logs:job:{job_id}")
        await pubsub.close()
        await valkey.close()
