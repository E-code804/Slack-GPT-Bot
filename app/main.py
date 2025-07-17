# FastAPI server entry
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

        # Fetch PR data from GitHub API
        github_api_url = (
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(github_api_url)
            pr_data = resp.json()

        # Build response message
        title = pr_data["title"]
        author = pr_data["user"]["login"]
        state = pr_data["state"]
        html_url = pr_data["html_url"]

        return PlainTextResponse(
            f"📌 *{title}*\n👤 Author: {author}\n🔗 {html_url}\n📂 Status: {state}",
            status_code=200,
        )

    except Exception as e:
        return PlainTextResponse(f"Error parsing PR link: {str(e)}", status_code=200)
