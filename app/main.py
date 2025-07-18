# FastAPI server entry
import os
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Form
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
async def handle_summarizepr(
    request: Request,
    text: str = Form(...),
    response_url: str = Form(...),  # Provided by Slack.
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    # Ensure valid GitHub PR link
    if "github.com" not in text or "/pull/" not in text:
        return PlainTextResponse(
            "Please provide a valid GitHub PR link.", status_code=200
        )

    # Queue summary work in a background task
    background_tasks.add_task(process_pr_summary, text, response_url)

    # Return an immediate response to respect slack's timeout rule
    immediate_resp = (
        "🔄 Analyzing PR... This may take a moment. I'll update you shortly!"
    )

    return PlainTextResponse(immediate_resp, status_code=200)


async def process_pr_summary(pr_url: str, response_url: str):
    """Background task to process PR and send result back to Slack"""
    try:
        parts = pr_url.split("/")
        owner, repo, pr_number = parts[3], parts[4], parts[6]

        github_token = os.getenv("GITHUB_TOKEN")
        headers = {}
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        async with httpx.AsyncClient(timeout=30.0) as client:
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
            files_changed = pr_data.get("changed_files", 0)  # Files changed count
            additions = pr_data.get("additions", 0)
            deletions = pr_data.get("deletions", 0)

            # print(f"PR Title: {title}")
            # print(f"PR Description: {description}")
            # print(f"Files changed: {files_changed}")
            # print(f"Additions: +{additions}, Deletions: -{deletions}")
            # print(f"Diff content length: {len(diff_content)} characters")

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

            # Send the response text back to slack using the response url
            await send_to_slack_response_url(response_url, response_text)

            return PlainTextResponse(response_text, status_code=200)

    except Exception as e:
        error_msg = f"❌ Error analyzing PR: {str(e)}"
        await send_to_slack_response_url(response_url, error_msg)


async def send_to_slack_response_url(response_url: str, response_text: str):
    # Send delated response back to slack
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "text": response_text,
                "response_type": "in_channel",  # or "ephemeral" for private
            }
            await client.post(response_url, json=payload)
    except Exception as e:
        print(f"Failed to send response to Slack: {e}")
