from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import requests

app = FastAPI()

class Setting(BaseModel):
    label: str
    name: str
    type: str
    default: str
    required: bool

class IntegrationSpec(BaseModel):
    name: str
    description: str
    interval: int
    target_url: str
    tick_url: str
    settings: List[Setting]

@app.get("/integration-spec", response_model=IntegrationSpec)
def get_integration_spec():
    return {
        "name": "DependencyTracker",
        "description": "Monitors pull requests for changes to requirements.txt and notifies the channel after 24 hours.",
        "interval": 86400,
        "target_url": "https://your-server.com/target",
        "tick_url": "https://your-server.com/tick",
        "settings": [
            {
                "label": "GitHub Repository URL",
                "name": "repo_url",
                "type": "text",
                "default": "",
                "required": True
            },
            {
                "label": "Telex Webhook URL",
                "name": "telex_webhook_url",
                "type": "text",
                "default": "",
                "required": True
            },
        ]
    }

def fetch_file_content(url: str, headers: dict = None):
    """Fetch file content from GitHub API."""
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('content', '')
    return None

@app.post("/tick")
def tick_handler(repo_url: str, telex_webhook_url: str):
    """Checks PRs for requirements.txt changes and notifies Telex if changes exist."""
    # Extract GitHub username and repository name from the URL
    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    
    username, repo_name = parts[-2], parts[-1]

    # GitHub API endpoint to list pull requests
    pulls_url = f'https://api.github.com/repos/{username}/{repo_name}/pulls'
    response = requests.get(pulls_url)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch pull requests")

    pull_requests = response.json()

    for pr in pull_requests:
        pr_number = pr['number']
        pr_branch = pr['head']['ref']

        # GitHub API endpoint to get requirements.txt content from PR branch and main branch
        headers = {"Accept": "application/vnd.github.v3+json"}
        pr_file_url = f'https://api.github.com/repos/{username}/{repo_name}/contents/requirements.txt?ref={pr_branch}'
        main_file_url = f'https://api.github.com/repos/{username}/{repo_name}/contents/requirements.txt?ref=main'

        pr_file_content = fetch_file_content(pr_file_url, headers)
        main_file_content = fetch_file_content(main_file_url, headers)

        if pr_file_content and main_file_content and pr_file_content != main_file_content:
            message = f"Pull Request #{pr_number} contains changes to requirements.txt."
            requests.post(telex_webhook_url, json={"message": message})

    return {"status": "success", "message": "Checked PRs for requirements.txt changes"}
