# FastAPI server entry
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, Header, Request, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from services.cache_service import update_pr_state_cache
from utils.server_utils import extract_pr_merge_info
from services.pr_service import PRService

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

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

# Initialize services & client
pr_service = PRService()
client = WebClient(token=os.getenv("BOT_USER_OAUTH_TOKEN"))


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


# TODO - send message in slack channel when a PR is made
@app.post("/github/postprs")
async def handle_github_pr_action(
    request: Request,
    x_github_event: str = Header(...),
):
    try:
        payload = await request.json()
        if not payload:
            print("Received empty body from GitHub webhook")
            return {"status": "ignored", "message": "Empty request body"}

        pr_action = payload.get("action", None)
        pr_info = payload.get("pull_request", None)
        if not pr_action or not pr_info:
            return {"status": "error", "message": "Missing PR action/info."}

        pr_url = pr_info.get("html_url", None)
        if not pr_url:
            return {"status": "error", "message": "Missing PR URL."}

        try:
            slack_message = f"PR {pr_action} at {pr_url}"
            # Send to slack
            result = client.chat_postMessage(
                channel=os.getenv("SLACK_GPT_BOT_CHANNEL_ID"),
                text=slack_message,
            )

            if result["ok"]:
                print(f"Slack message sent successfully: {result['ts']}")
                return {
                    "status": "Success",
                    "message": "Succeeded to send Slack message",
                }
            else:
                print(f"Slack API returned error: {result}")
                return {
                    "status": "error",
                    "message": "Failed to send Slack message",
                }

        except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}")
            return {
                "status": "error",
                "message": f"Slack API error: {e.response['error']}",
            }
        except Exception as e:
            print(f"Unexpected error sending Slack message: {e}")
            return {
                "status": "error",
                "message": "Failed to send Slack notification",
            }

        # TODO update the pr cache w/ the pr_action

        # Handle other event types
        print(f"Received GitHub event '{x_github_event}' - no action taken")
        return {
            "status": "ignored",
            "message": f"Event '{x_github_event}' not processed",
        }
    except Exception as e:
        print(f"Unexpected error in GitHub webhook handler: {e}")
        return {"status": "error", "message": "Internal server error"}


# Github Webhooks
@app.post("/github/postpushes")
async def handle_github_push(request: Request, x_github_event: str = Header(...)):
    try:
        payload = await request.json()
        if not payload:
            print("Received empty body from GitHub webhook")
            return {"status": "ignored", "message": "Empty request body"}

        # Handle ping events for route verification
        if x_github_event == "ping":
            print("Received GitHub webhook ping")
            return {"status": "pong", "message": "Webhook configured successfully"}

        # Usage in your webhook handler:
        if x_github_event == "push":
            merge_info = extract_pr_merge_info(payload, x_github_event)

            if merge_info["is_pr_merge"]:
                try:
                    slack_message = f"PR #{merge_info['pr_number']} merged from branch '{merge_info['branch_name']}'"
                    print(slack_message)
                    # Send to slack
                    result = client.chat_postMessage(
                        channel=os.getenv("SLACK_GPT_BOT_CHANNEL_ID"),
                        text=slack_message,
                    )

                    if result["ok"]:
                        print(f"Slack message sent successfully: {result['ts']}")
                    else:
                        print(f"Slack API returned error: {result}")
                        return {
                            "status": "error",
                            "message": "Failed to send Slack message",
                        }

                except SlackApiError as e:
                    print(f"Slack API error: {e.response['error']}")
                    return {
                        "status": "error",
                        "message": f"Slack API error: {e.response['error']}",
                    }
                except Exception as e:
                    print(f"Unexpected error sending Slack message: {e}")
                    return {
                        "status": "error",
                        "message": "Failed to send Slack notification",
                    }

                # Update the cache if pr_url already exists. ADD ERROR FOR THIS TOO.
                try:
                    cache_updated = await update_pr_state_cache(
                        merge_info["pr_url"], "merged"
                    )
                    if cache_updated:
                        print(f"Cache updated for PR: {merge_info['pr_url']}")
                    else:
                        print(f"No existing cache found for PR: {merge_info['pr_url']}")
                except Exception as e:
                    print(
                        f"Failed to update cache for PR {merge_info.get('pr_url')}: {e}"
                    )
                    # Don't return error - cache update failure shouldn't fail the webhook

                return {
                    "status": "success",
                    "message": "PR merge processed and Slack notification sent",
                    "pr_number": merge_info["pr_number"],
                }
            else:
                print(f"Push event received but not a PR merge: {payload.get('ref')}")
                return {"status": "ignored", "message": "Push event but not a PR merge"}

        # Handle other event types
        print(f"Received GitHub event '{x_github_event}' - no action taken")
        return {
            "status": "ignored",
            "message": f"Event '{x_github_event}' not processed",
        }
    except Exception as e:
        print(f"Unexpected error in GitHub webhook handler: {e}")
        return {"status": "error", "message": "Internal server error"}


@app.post("/github/postprreviews")
async def handle_github_pr_reviews(
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
