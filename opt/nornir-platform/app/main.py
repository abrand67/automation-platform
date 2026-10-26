import uuid
import json
import asyncio
import zmq
import zmq.asyncio
import redis.asyncio as aioredis
from datetime import timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from schemas import AutomationJobRequest
from database import get_db_session, JobExecution, User
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

app = FastAPI(title="Nornir Platform Enterprise Automation Engine")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

ZMQ_URL = "tcp://127.0.0.1:5555"
VALKEY_URL = "redis://127.0.0.1:6379/0"

zmq_context = zmq.asyncio.Context()
zmq_socket = zmq_context.socket(zmq.PUSH)

allow_operators = RoleChecker(["admin", "operator"])

@app.on_event("startup")
async def startup_event():
    zmq_socket.bind(ZMQ_URL)
    await scheduler.start_in_background()

@app.get("/login", response_class=HTMLResponse)
async def get_login_gateway_page(request: Request):
    """
    Serves the unauthenticated centralized user interface login card wrapper.
    """
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/logout", response_class=HTMLResponse)
async def process_platform_logout(request: Request):
    """
    Serves a simple, instant landing page that instructs the browser 
    to wipe localized token caches before sending the user back to the gateway.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><link rel="stylesheet" href="/static/style.css"></head>
    <body style="display:flex; justify-content:center; align-items:center; min-height:80vh;">
        <div style="font-family:monospace; text-align:center; color:var(--text-muted);">
            <p>[System] Flushing secure credential parameters out of memory cache...</p>
        </div>
        <script>
            // Flush the secure verification token out of browser storage arrays instantly
            localStorage.removeItem("nornir_access_token");
            // Redirect the client context straight back to the login barrier gateway
            window.location.href = "/login";
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/inventories", response_class=HTMLResponse)
async def list_inventories_component_pane(request: Request):
    """
    Serves the raw HTML component fragment summarizing NetBox fleet scopes.
    Intended for dynamic intercept injection via HTMX swaps.
    """
    return templates.TemplateResponse("inventories_pane.html", {"request": request})

@app.get("/projects", response_class=HTMLResponse)
async def list_projects_component_pane(request: Request):
    """
    Serves the raw HTML component fragment tracking GitLab workspace paths.
    Intended for dynamic intercept injection via HTMX swaps.
    """
    return templates.TemplateResponse("projects_pane.html", {"request": request})


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def get_job_dashboard(request: Request, job_id: str):
    """Serves the base HTMX monitoring console layout."""
    return templates.TemplateResponse("dashboard.html", {"request": request, "job_id": job_id})

@app.post("/api/v1/auth/token", response_model=dict)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db_session)
):
    """Processes directory-integrated authentication handshakes."""
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
            detail="Authentication failed across directory providers.",
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
    current_user: User = Depends(get_current_user),
    has_clearance: bool = Depends(ObjectPermissionGuard(object_type="project", action="write"))
):
    """Clones or pulls targeted GitLab repository code onto local workspace scopes."""
    try:
        loop = asyncio.get_event_loop()
        project_path = await loop.run_in_executor(
            None, sync_gitlab_project, project_id, repo_url, branch, gitlab_token
        )
        return {"status": "SUCCESS", "project_id": project_id, "synchronized_path": project_path}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

verify_project_execution = ObjectPermissionGuard(object_type="project", action="execute")

@app.post("/api/v1/projects/{project_id}/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_source_controlled_job(
    project_id: str,
    payload: AutomationJobRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    has_clearance: bool = Depends(verify_project_execution)
):
    """Dispatches source-controlled tasks over local ZeroMQ distribution paths."""
    job_id = str(uuid.uuid4())
    new_job = JobExecution(id=job_id, job_type=payload.job_type, status="DISPATCHED", filters=payload.netbox_filters)
    db.add(new_job)
    await db.commit()

    job_message = {
        "job_id": job_id,
        "project_id": project_id,
        "task": payload.job_type,
        "netbox_filters": payload.netbox_filters,
        "extra_vars": payload.extra_vars
    }
    await zmq_socket.send_json(job_message)
    return {"job_id": job_id, "status": "DISPATCHED", "initiated_by": current_user.username}

@app.post("/api/v1/jobs", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(allow_operators)])
async def legacy_trigger_automation_job(payload: AutomationJobRequest, db: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    """Legacy global-role path fallback endpoint handling direct localized automation requests."""
    job_id = str(uuid.uuid4())
    new_job = JobExecution(id=job_id, job_type=payload.job_type, status="DISPATCHED", filters=payload.netbox_filters)
    db.add(new_job)
    await db.commit()

    job_message = {
        "job_id": job_id,
        "project_id": "global",
        "task": payload.job_type,
        "netbox_filters": payload.netbox_filters,
        "extra_vars": payload.extra_vars
    }
    await zmq_socket.send_json(job_message)
    return {"job_id": job_id, "status": "DISPATCHED", "initiated_by": current_user.username}

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

@app.websocket("/ws/v1/jobs/{job_id}/logs")
async def stream_job_logs(websocket: WebSocket, job_id: str, db: AsyncSession = Depends(get_db_session)):
    """
    Subscribes to Percona Valkey log channels, dynamically validating user access
    via incoming URL query parameters to enforce multi-tenant streaming boundaries.
    """
    await websocket.accept()

    # Extract, parse, and validate token parameter string out of query properties
    token_str = websocket.query_params.get("token")
    user = await get_ws_current_user(token=token_str, db=db) if token_str else None

    if not user:
        # Reject unauthenticated connections instantly, keeping resource pools safe
        await websocket.send_text("""
        <div id="terminal-log-output" hx-swap-oob="beforeend">
            <div class="text-rose-400 font-semibold">[Security] Connection Refused. Invalid or missing WebSocket token.</div>
        </div>
        """)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    valkey = aioredis.from_url(VALKEY_URL, decode_responses=True)
    pubsub = valkey.pubsub()
    await pubsub.subscribe(f"logs:job:{job_id}")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                log_payload = json.loads(message["data"])
                raw_text = log_payload.get("message", "")

                color_class = "text-slate-300"
                if "❌" in raw_text or "CRITICAL" in raw_text:
                    color_class = "text-rose-400 font-semibold"
                elif "✅" in raw_text:
                    color_class = "text-emerald-400 font-semibold"

                html_snippet = f"""
                <div id="terminal-log-output" hx-swap-oob="beforeend">
                    <div class="{color_class} text-xs"><span class="text-slate-600 mr-2">>>></span>{raw_text}</div>
                </div>
                """
                await websocket.send_text(html_snippet)
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"logs:job:{job_id}")
        await pubsub.close()
        await valkey.close()

