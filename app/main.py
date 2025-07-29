# FastAPI server entry
from fastapi import BackgroundTasks, FastAPI, HTTPException, Header, Request, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from services.pr_service import PRService

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

# Initialize services
pr_service = PRService()


# Health check point
@app.get("/ping")
async def ping():
    return {"pong": "pong"}


# Slack verification
@app.post("/")
async def challenge(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Step 1: Handle URL verification
    if payload.get("type") == "url_verification":
        return JSONResponse(content={"challenge": payload.get("challenge")})

    # Step 2: Handle actual Slack events

    return {"status": "ok"}


# For PR link summarization. Validate, queue tasks, and send immediate response.
@app.post("/slack/summarizepr")
async def handle_summarizepr(
    request: Request,
    text: str = Form(...),
    response_url: str = Form(...),  # Provided by Slack.
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    if "github.com" not in text or "/pull/" not in text:
        return PlainTextResponse(
            "Please provide a valid GitHub PR link.", status_code=200
        )

    background_tasks.add_task(pr_service.process_pr_summary, text, response_url)
    immediate_resp = (
        "🔄 Analyzing PR... This may take a moment. I'll update you shortly!"
    )

    return PlainTextResponse(immediate_resp, status_code=200)


# Github Webhooks
@app.post("/github/postpushes")
async def handle_github_push(
    request: Request,
    x_github_event: str = Header(...),
    x_github_delivery: str = Header(...),
    x_hub_signature_256: str = Header(...),
):
    payload = await request.json()

    print(f"Event: {x_github_event}")
    print(f"Delivery ID: {x_github_delivery}")
    print(f"Signature: {x_hub_signature_256}")
    print(f"Payload: {payload}")

    return {"status": "received"}


@app.post("/github/postprs")
async def handle_github_push(
    request: Request,
    x_github_event: str = Header(...),
    x_github_delivery: str = Header(...),
    x_hub_signature_256: str = Header(...),
):
    payload = await request.json()

    print(f"Event: {x_github_event}")
    print(f"Delivery ID: {x_github_delivery}")
    print(f"Signature: {x_hub_signature_256}")
    print(f"Payload: {payload}")

    return {"status": "received"}


@app.post("/github/postprreviews")
async def handle_github_push(
    request: Request,
    x_github_event: str = Header(...),
    x_github_delivery: str = Header(...),
    x_hub_signature_256: str = Header(...),
):
    payload = await request.json()

    print(f"Event: {x_github_event}")
    print(f"Delivery ID: {x_github_delivery}")
    print(f"Signature: {x_hub_signature_256}")
    print(f"Payload: {payload}")

    return {"status": "received"}
