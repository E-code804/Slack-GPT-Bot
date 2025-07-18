# FastAPI server entry
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai_summary import PRSummarizer
import httpx

# Load env variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="Slack GPT Bot Server")

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or ["*"] to allow any origin
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # Allow all headers (e.g. Content-Type)
)


# Health check point
@app.get("/ping")
async def ping():
    return {"pong": "pong"}


# Slack verification
@app.post("/")
async def challenge(request: Request):
    payload = await request.json()

    # Step 1: Handle URL verification
    if payload.get("type") == "url_verification":
        return JSONResponse(content={"challenge": payload.get("challenge")})

    # Step 2: Handle actual Slack events
    # Add your event handling logic here

    return {"status": "ok"}


# For PR links
@app.post("/slack/summarizepr")
async def handle_summarizepr(request: Request, text: str = Form(...)):
    # Ensure valid GitHub PR link
    if "github.com" not in text or "/pull/" not in text:
        return PlainTextResponse(
            "Please provide a valid GitHub PR link.", status_code=200
        )

    # Basic for now, extract info from PR link.
    try:
        parts = text.split("/")
        owner, repo, pr_number = parts[3], parts[4], parts[6]

        github_token = os.getenv("GITHUB_TOKEN")
        headers = {}
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        async with httpx.AsyncClient() as client:
            # Fetch PR data
            github_api_url = (
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            )
            pr_resp = await client.get(github_api_url, headers=headers)
            pr_data = pr_resp.json()

            # Fetch PR diff
            diff_headers = headers.copy()
            diff_headers["Accept"] = "application/vnd.github.v3.diff"
            diff_resp = await client.get(github_api_url, headers=diff_headers)
            diff_content = diff_resp.text

            # Extract relevant info
            title = pr_data["title"]
            description = pr_data["body"] or "No description provided"
            author = pr_data["user"]["login"]
            state = pr_data["state"]
            html_url = pr_data["html_url"]

            # Files changed count
            files_changed = pr_data.get("changed_files", 0)
            additions = pr_data.get("additions", 0)
            deletions = pr_data.get("deletions", 0)

            print(f"PR Title: {title}")
            print(f"PR Description: {description}")
            print(f"Files changed: {files_changed}")
            print(f"Additions: +{additions}, Deletions: -{deletions}")
            print(f"Diff content length: {len(diff_content)} characters")

            # Use OpenAI to summarize the PR
            summarizer = PRSummarizer()
            summary = summarizer.summarize_pr(title, description, diff_content)
            # formatted_summary = summarizer.format_summary_for_slack(summary)

            # Return the AI-generated summary
            response_text = f"👤 **Author:** {author}\n"
            response_text += (
                f"📊 **Changes:** {files_changed} files, +{additions}/-{deletions}\n"
            )
            response_text += f"🔗 **Link:** {html_url}\n"
            response_text += f"📂 **Status:** {state}\n\n"
            response_text += summary

            return PlainTextResponse(response_text, status_code=200)

    except Exception as e:
        return PlainTextResponse(f"Error parsing PR link: {str(e)}", status_code=200)


def parse_diff_for_files(diff_content):
    """Extract file names and their change types from diff content"""
    files_changed = []
    lines = diff_content.split("\n")

    for line in lines:
        if line.startswith("diff --git"):
            # Extract file path: diff --git a/path/to/file.py b/path/to/file.py
            parts = line.split()
            if len(parts) >= 4:
                file_path = parts[2][2:]  # Remove 'a/' prefix
                files_changed.append(file_path)

    return files_changed


def extract_meaningful_changes(diff_content):
    """Extract the actual code changes (additions/deletions) from diff"""
    lines = diff_content.split("\n")
    changes = []
    current_file = None

    for line in lines:
        if line.startswith("diff --git"):
            # New file
            parts = line.split()
            if len(parts) >= 4:
                current_file = parts[2][2:]  # Remove 'a/' prefix
        elif line.startswith("@@"):
            # Hunk header - shows line numbers
            continue
        elif line.startswith("+") and not line.startswith("+++"):
            # Addition
            changes.append(
                {
                    "file": current_file,
                    "type": "addition",
                    "content": line[1:],  # Remove + prefix
                }
            )
        elif line.startswith("-") and not line.startswith("---"):
            # Deletion
            changes.append(
                {
                    "file": current_file,
                    "type": "deletion",
                    "content": line[1:],  # Remove - prefix
                }
            )

    return changes
