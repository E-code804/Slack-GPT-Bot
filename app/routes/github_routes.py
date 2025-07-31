import os
from typing import Any, Dict

from fastapi import APIRouter, Request, Header

from services.pr_service import PRService
from services.cache_service import update_pr_state_cache

from utils.server_utils import extract_pr_merge_info

router = APIRouter()
pr_service = PRService()


# Github Webhooks
# Handles notifiying slack channel when a PR is made.
@router.post("/postpushes")
async def handle_github_push(request: Request, x_github_event: str = Header(...)):
    try:
        # Handle ping events for route verification
        if x_github_event == "ping":
            print("Received GitHub webhook ping")
            return {"status": "pong", "message": "Webhook configured successfully"}

        payload = await request.json()
        if not payload:
            print("Received empty body from GitHub webhook")
            return {"status": "ignored", "message": "Empty request body"}

        # Usage in your webhook handler:
        if x_github_event == "push":
            merge_info = extract_pr_merge_info(payload, x_github_event)

            if merge_info["is_pr_merge"]:
                # Send message to slack channel
                slack_msg = f"PR #{merge_info['pr_number']} merged from branch '{merge_info['branch_name']}'"
                channel = os.getenv("SLACK_GPT_BOT_CHANNEL_ID")
                slack_result = await pr_service.send_msg_to_slack_channel(
                    slack_msg, channel
                )
                if slack_result["status"] == "error":
                    print(f"Failed to send Slack message: {slack_result['message']}")
                    return {"status": "error", "message": slack_result["message"]}

                # Update the pr cache w/ the pr_action
                cache_result = await update_pr_state_cache(
                    pr_url=merge_info["pr_url"], new_state="merged"
                )
                handle_cache_logging(cache_result=cache_result)

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


# Handles notifying slack channel when PR actions such as closing (when merged or forcefully) and reopening are made.
@router.post("/postprs")
async def handle_github_pr_action(
    request: Request,
    x_github_event: str = Header(...),
):
    try:
        # Handle ping events for route verification
        if x_github_event == "ping":
            print("Received GitHub webhook ping")
            return {"status": "pong", "message": "Webhook configured successfully"}

        # Handle verification of required information.
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

        # Send message to slack channel
        slack_msg = f"PR {pr_action} at {pr_url}"
        channel = os.getenv("SLACK_GPT_BOT_CHANNEL_ID")
        slack_result = await pr_service.send_msg_to_slack_channel(slack_msg, channel)
        if slack_result["status"] == "error":
            print(f"Failed to send Slack message: {slack_result['message']}")
            return {"status": "error", "message": slack_result["message"]}

        # Update the pr cache w/ the pr_action
        cache_result = await update_pr_state_cache(pr_url, pr_action)
        handle_cache_logging(cache_result=cache_result)

        print(f"Received GitHub event '{x_github_event}'.")
        return {
            "status": "success",
            "message": f"Event '{x_github_event}' processed - message sent!",
        }
    except Exception as e:
        print(f"Unexpected error in GitHub webhook handler: {e}")
        return {"status": "error", "message": "Internal server error"}


@router.post("/postprreviews")
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


def handle_cache_logging(cache_result: Dict[str, Any]) -> None:
    if cache_result["status"] == "success":
        print(f"Cache updated: {cache_result['message']}")
    elif cache_result["status"] == "ignored":
        print(f"Cache update skipped: {cache_result['message']}")
    elif cache_result["status"] == "error":
        print(f"Cache update failed: {cache_result['message']}")
        # Don't return error - cache failures shouldn't stop webhook processing
