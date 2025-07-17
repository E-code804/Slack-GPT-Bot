# FastAPI server entry
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    print(text)
    return {text}
