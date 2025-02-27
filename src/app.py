import os
import logging
import hmac 
import hashlib
import json
import requests
import jwt
import git 
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Load environment variables
logging.basicConfig(level=logging.DEBUG)

PRIVATE_KEY = os.getenv('GITHUB_PRIVATE_KEY')
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET').strip()
APP_ID = os.getenv('GITHUB_APP_IDENTIFIER')
# GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
# REPO_NAME = os.getenv('REPO_NAME')

# # Initialize GitHub client
# github = Github(GITHUB_TOKEN)
# repo = github.get_repo(REPO_NAME)


async def payload_fetcher(request: Request):
    return await request.json()

def get_payload_request_signature(payload):
    return payload['headers']['X-Hub-Signature-256']

async def verify_signature_dependency(request: Request, x_hub_signature_256: str = Header(None)):
    payload = await request.body()
    secret_token = WEBHOOK_SECRET
    verify_signature(payload, secret_token, x_hub_signature_256)

def verify_signature(payload, secret_token, sig_hdr):
    if not sig_hdr:
        logging.error("x-hub-signature-256 header is missing!")
        raise HTTPException(status_code=403, detail="x-hub-signature-256 header is missing!")
    
    if not secret_token:
        logging.error("Webhook secret is not set")
        raise HTTPException(status_code=500, detail="Webhook secret is not set")
    
    hash_object = hmac.new(secret_token.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    logging.debug(f"Expected signature: {expected_signature}")
    logging.debug(f"Received signature: {sig_hdr}")
    
    if not hmac.compare_digest(expected_signature, sig_hdr):
        logging.error("Request signatures didn't match!")
        raise HTTPException(status_code=403, detail="Request signatures didn't match!")
    
    return True

async def auth_app_dep():
    return await authenticate_app()

async def authenticate_app():
    # Generate JWT
    app_id = APP_ID
    private_key = PRIVATE_KEY.replace("\\n", "\n")  # Ensure the private key is correctly formatted

    now = datetime.utcnow()
    payload = {
        'iat': now,
        'exp': now + timedelta(minutes=10),
        'iss': app_id
    }

    jwt_token = jwt.encode(payload, private_key, algorithm='RS256')

    # Get installation ID
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    response = requests.get('https://api.github.com/app/installations', headers=headers)
    response.raise_for_status()
    installations = response.json()
    installation_id = installations[0]['id']  # Assuming you want the first installation

    # Create installation access token
    token_url = f'https://api.github.com/app/installations/{installation_id}/access_tokens'
    response = requests.post(token_url, headers=headers)
    response.raise_for_status()
    token = response.json()['token']

    return token

def clone_repository(full_repo_name, repository, ref, token):
    # Clone the repository
    repo_url = f"https://x-access-token:{token}@github.com/{full_repo_name}.git"
    repo = git.Repo.clone_from(repo_url, repository)

    # Change to the repository directory
    original_dir = os.getcwd()
    os.chdir(repository)

    # Pull the latest changes and checkout the specified ref
    repo.git.pull()
    repo.git.checkout(ref)

    # Change back to the original directory
    os.chdir(original_dir)

def handle_push_event(payload):
    # Example: Print commit messages
    for commit in payload['commits']:
        print(f"Commit message: {commit['message']}")

def update_check_run(token, repo_full_name, check_run_id, status, conclusion=None):
    url = f"https://api.github.com/repos/{repo_full_name}/check-runs/{check_run_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "status": status
    }
    if conclusion:
        data["conclusion"] = conclusion
    response = requests.patch(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def initiate_check_run(token, repo_full_name, run_id, head_sha):
    update_check_run(token, repo_full_name, run_id, "in_progress")
    update_check_run(token, repo_full_name, run_id, "completed", "success")



def create_check_run(token, repo_full_name, head_sha):
    logging.debug(f"Creating check run for {head_sha}")
    logging.debug(f"Repo full name: {repo_full_name}")
    url = f"https://api.github.com/repos/{repo_full_name}/check-runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {
        "name": "Code SA Run",
        "head_sha": head_sha,
        "status": "in_progress",
        "started_at": datetime.utcnow().isoformat() + "Z"
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

@app.get("/")
async def root():
    return {"message": "Hello, this is CodeSA App!"}

@app.post("/webhook")
async def webhook(request: Request, x_github_event: str = Header(None),
                  verified: bool = Depends(verify_signature_dependency),
                  token: str = Depends(auth_app_dep),
                  payload: dict = Depends(payload_fetcher)):

    logging.debug(f"Received GitHub event: {x_github_event}")
    if x_github_event == 'push':
        handle_push_event(payload)
    # Add more event handlers as needed

    if x_github_event  in ['check_run', 'check_suite']:
        if x_github_event == 'check_suite':
            head_sha = payload["check_suite"]["head_sha"]
            id = payload["check_suite"]["id"]
        elif x_github_event == 'check_run':
            head_sha = payload["check_run"]["head_sha"]
            id = payload["check_run"]["id"]

        logging.debug("Payload action: %s", payload["action"])
        repo_name = payload["repository"]["full_name"]
        if payload["action"] in ["requested", "rerequested"]:
            response = create_check_run(token, repo_name, head_sha)
            logging.debug("Check run created: %s", response)
        elif payload["action"] == "created":
            logging.debug("Check run created: %s", payload["check_run"])
            initiate_check_run(token, repo_name, id, head_sha)
    return JSONResponse(content={"status": "success"})


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=3000)