from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


app = FastAPI()

BASE_URL = os.getenv("BASE_URL")
# TELEX_WEBHOOK_URL = os.getenv("TELEX_WEBHOOK")
TARGET_URL = os.getenv("TARGET_URL")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Setting(BaseModel):
    label: str
    name: str
    type: str
    default: str
    required: bool

class MonitorPayload(BaseModel):
    channel_id: str
    return_url: str
    settings: List[Setting]

@app.get("/integration.json")
def get_integration_spec():
    return {
        "data": {
            "date": {"created_at": "2025-02-20", "updated_at": "2025-02-20"},
            "descriptions": {
                "app_name": "DependencyTracker",
                "app_description": "Monitors pull requests for changes to requirements.txt and notifies the channel after 24 hours.",
                "app_logo": "https://avatars.githubusercontent.com/u/27347476?s=280&v=4",
                "app_url": BASE_URL,
                "background_color": "#fff"
            },
            "is_active": True,
            "integration_type": "interval",
            "integration_category": "Email & Messaging",
            "key_features": ["github", "dependency tracker", "requirements.txt"],
            "author": "Godstime01",
            "settings": [
                {
                    "label": "interval",
                    "type": "dropdown",
                    "required": True,
                    "default": "Daily",
                    "options": ["Daily", "Weekly", "Monthly"]
                },
                {
                    "label": "Github Repository URL",
                    "type": "text",
                    "description": "Link to the reposistory you intend tracking",
                    "required": True,
                }
            ],
            "target_url": BASE_URL,
            "tick_url": f"{BASE_URL}/tick"
        }
    }

def fetch_file_content(url: str, headers: dict = None):
    """Fetch file content from GitHub API."""
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('content', '')
    return None

@app.post("/tick", status_code=202)
def tick_handler(payload: MonitorPayload, background_tasks: BackgroundTasks):
    """Checks the latest PR for requirements.txt changes and notifies Telex if changes exist."""
    
    def process_monitoring():
        github_url = [s.default for s in payload.settings if s.label.startswith("Github")][0]
        parts = github_url.rstrip('/').split('/')
        if len(parts) < 2:
            return
        
        username, repo_name = parts[-2], parts[-1]

        pulls_url = f'https://api.github.com/repos/{username}/{repo_name}/pulls?sort=updated&direction=desc&per_page=1'
        response = requests.get(pulls_url)

        if response.status_code != 200:
            return

        pull_requests = response.json()
        if not pull_requests:
            return
        
        latest_pr = pull_requests[0]
        pr_number = latest_pr['number']
        pr_branch = latest_pr['head']['ref']

        headers = {"Accept": "application/vnd.github.v3+json"}
        pr_file_url = f'https://api.github.com/repos/{username}/{repo_name}/contents/requirements.txt?ref={pr_branch}'
        main_file_url = f'https://api.github.com/repos/{username}/{repo_name}/contents/requirements.txt?ref=main'

        pr_file_content = fetch_file_content(pr_file_url, headers)
        main_file_content = fetch_file_content(main_file_url, headers)

        if pr_file_content and main_file_content and pr_file_content != main_file_content:
            message = f"Latest Pull Request #{pr_number} contains changes to requirements.txt."
            requests.post(payload.return_url, json={"message": message})

    # Add background task
    background_tasks.add_task(process_monitoring)

    return {"status": "accepted"}
