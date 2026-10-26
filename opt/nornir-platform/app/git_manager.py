# file: git_manager.py
import os
import subprocess
import shutil

WORKSPACE_ROOT = "/opt/nornir-platform/workspaces"

def sync_gitlab_project(project_id: str, repo_url: str, branch: str = "main", token: str = None):
    """
    Clones or pulls a targeted GitLab repository into an isolated local tracking folder.
    Replaces static local script restrictions with dynamic source control management.
    """
    # Inject GitLab Personal Access Token for private repositories if provided
    if token and "gitlab.com" in repo_url and "@" not in repo_url:
        repo_url = repo_url.replace("https://", f"https://oauth2:{token}@")

    project_dir = os.path.join(WORKSPACE_ROOT, f"project_{project_id}")
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)

    if not os.path.exists(project_dir):
        # Perform initial clean repository isolation clone
        cmd = ["git", "clone", "-b", branch, repo_url, project_dir]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"GitLab Clone Failure: {result.stderr}")
    else:
        # Repository exists; execute an atomic fetch and hard reset to match production branch head
        cmd_fetch = ["git", "-C", project_dir, "fetch", "--all"]
        cmd_reset = ["git", "-C", project_dir, "reset", "--hard", f"origin/{branch}"]
        
        subprocess.run(cmd_fetch, capture_output=True)
        result = subprocess.run(cmd_reset, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"GitLab Pull Reset Failure: {result.stderr}")

    return project_dir

