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
import subprocess

WORKSPACE_ROOT = "/opt/Fluxara/workspaces"

def sync_gitlab_project(project_id: str, repo_url: str, branch: str = "main", token: str = None):
    if token and "gitlab.com" in repo_url and "@" not in repo_url:
        repo_url = repo_url.replace("https://", f"https://oauth2:{token}@")
    project_dir = os.path.join(WORKSPACE_ROOT, f"project_{project_id}")
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)

    if not os.path.exists(project_dir):
        cmd = ["git", "clone", "-b", branch, repo_url, project_dir]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0: raise Exception(f"Git Clone Failure: {result.stderr}")
    else:
        cmd_fetch = ["git", "-C", project_dir, "fetch", "--all"]
        cmd_reset = ["git", "-C", project_dir, "reset", "--hard", f"origin/{branch}"]
        subprocess.run(cmd_fetch, capture_output=True)
        result = subprocess.run(cmd_reset, capture_output=True, text=True)
        if result.returncode != 0: raise Exception(f"Git Pull Reset Failure: {result.stderr}")
    return project_dir
