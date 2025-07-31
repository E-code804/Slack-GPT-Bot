# FastAPI server entry
from fastapi import FastAPI, HTTPException, Header, Request, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from routes import slack_routes, github_routes

# Initialize FastAPI
app = FastAPI(title="Slack GPT Bot Server")

origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or ["*"] to allow any origin
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # Allow all headers (e.g. Content-Type)
)

# Include the routes for Slack and Github.
app.include_router(slack_routes.router, prefix="/slack", tags=["Slack"])
app.include_router(github_routes.router, prefix="/github", tags=["GitHub"])


# Health check point
@app.get("/ping")
async def ping():
    return {"pong": "pong"}


# Slack verification - Handle Slack URL verification and events
@app.post("/")
async def slack_challenge(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Handle URL verification for Slack
    if payload.get("type") == "url_verification":
        return JSONResponse(content={"challenge": payload.get("challenge")})

    return {"status": "ok"}
