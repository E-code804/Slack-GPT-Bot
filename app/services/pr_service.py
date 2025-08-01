import asyncio
from dataclasses import dataclass
import os
from typing import Any, Dict, Optional, Tuple
import httpx

from services.openai_service import OpenAIService
from services.slack_service import SlackService
from services.cache_service import (
    del_pr_cache,
    get_pr_cache,
    set_pr_cache,
)

from utils.server_utils import get_response_text

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


@dataclass
class SlackMessageResult:
    status: str  # "success" or "error"
    message: str
    timestamp: Optional[str] = None
    channel: Optional[str] = None


class PRService:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.openai_service = OpenAIService()
        self.slack_service = SlackService()
        self.client = WebClient(token=os.getenv("BOT_USER_OAUTH_TOKEN"))

    # Handle sending messages to a slack channel
    async def send_msg_to_slack_channel(
        self, slack_message: str, channel: str, max_retries: int = 3
    ) -> SlackMessageResult:
        for attempt in range(1, max_retries + 1):
            try:
                # Send to slack
                result = self.client.chat_postMessage(channel=channel, text=slack_message)

                if result.get("ok"):
                    ts = result.get("ts", "No timestamp")
                    ch = result.get("channel", "No channel")
                    print(f"✅ Slack message sent successfully: {ts}")
                    return SlackMessageResult(
                        status="success",
                        message="Slack message sent successfully",
                        timestamp=ts,
                        channel=ch,
                    )
                else:
                    error = result.get("error", "Unknown error")
                    print(f"⚠️ Slack API error response: {error}")
                    return SlackMessageResult(
                        status="error",
                        message=f"Slack API error: {error}",
                    )

            except SlackApiError as e:
                status_code = e.response.status_code
                error_detail = e.response.get("error", "Unknown Slack API error")
                print(f"❌ Slack API error: {error_detail} (status: {status_code})")

                if status_code == 429 and attempt < max_retries:
                    retry_after = int(e.response.headers.get("Retry-After", "1"))
                    print(f"⏳ Rate limited. Retrying after {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    continue  # retry

                return SlackMessageResult(
                    status="error",
                    message=f"Slack API error: {error_detail}",
                )

            except Exception as e:
                print("❌ Unexpected error sending Slack message")
                return SlackMessageResult(
                    status="error",
                    message="Unexpected error sending Slack message",
                )

        # Fallback in case all retries fail
        return SlackMessageResult(
            status="error",
            message="Failed to send Slack message after retries",
        )

    # Background task to process PR and send result back to Slack
    async def process_pr_summary(self, pr_url: str, response_url: str) -> None:
        try:
            cached_summary = await get_pr_cache(pr_url=pr_url)
            response_text = ""

            # Send the response text back to slack using the response url
            if cached_summary:
                response_text = get_response_text(cached_summary)
            else:
                (pr_data, diff_content) = await self.fetch_pr(pr_url)
                response_text = await self.summarize_pr(pr_url, pr_data, diff_content)

            await self.slack_service.send_to_slack_response_url(response_url, response_text)

        except KeyError as key_error:
            error_msg = f"❌ Missing data in response: {str(key_error)}"
            print(f"KeyError in process_pr_summary: {key_error}")
            await self.slack_service.send_to_slack_response_url(response_url, error_msg)
            await del_pr_cache(pr_url)

        except httpx.HTTPStatusError as http_error:
            error_msg = f"❌ GitHub API error: {http_error.response.status_code}"
            print(f"HTTP error: {http_error}")
            await self.slack_service.send_to_slack_response_url(response_url, error_msg)
            await del_pr_cache(pr_url)

        except httpx.TimeoutException:
            error_msg = "❌ Request timed out. The PR might be too large."
            print("Timeout error in process_pr_summary")
            await self.slack_service.send_to_slack_response_url(response_url, error_msg)

        except Exception as e:
            error_msg = f"❌ Error analyzing PR: {str(e)}"
            print(f"Unexpected error in process_pr_summary: {e}")
            await self.slack_service.send_to_slack_response_url(response_url, error_msg)
            await del_pr_cache(pr_url)

    async def fetch_pr(self, pr_url: str) -> Tuple[Dict[str, Any], str]:
        parts = pr_url.split("/")

        try:
            owner, repo, pr_number = parts[3], parts[4], parts[6]
        except IndexError:
            raise ValueError(f"Invalid PR URL: {pr_url}")

        headers = {}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        else:
            raise ValueError("GitHub token not provided.")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch PR data
            github_api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            pr_resp = await client.get(github_api_url, headers=headers)
            pr_data = pr_resp.json()

            # Fetch PR diff content
            diff_headers = headers.copy()
            diff_headers["Accept"] = "application/vnd.github.v3.diff"
            diff_resp = await client.get(github_api_url, headers=diff_headers)
            diff_content = diff_resp.text

        return (pr_data, diff_content)

    async def summarize_pr(self, pr_url: str, pr_data: Dict[str, Any], diff_content: str) -> str:
        # Extract relevant info
        title = pr_data["title"] or "No title provided"
        description = pr_data["body"] or "No description provided"
        author = pr_data["user"]["login"] or "No author present"
        state = pr_data.get("state", "No state")
        html_url = pr_data.get("html_url", "No HTML URL")
        files_changed = pr_data.get("changed_files", 0)  # Files changed count
        additions = pr_data.get("additions", 0)
        deletions = pr_data.get("deletions", 0)

        # print_pr_info(title, description, files_changed, additions, deletions, diff_content)

        # Use OpenAI to summarize the PR
        summary = self.openai_service.summarize_pr(title, description, diff_content)

        response_dict = {
            "author": author,
            "files_changed": files_changed,
            "additions": additions,
            "deletions": deletions,
            "html_url": html_url,
            "state": state,
            "summary": summary,
        }

        # Set data in the cache
        await set_pr_cache(pr_url=pr_url, pr_dict=response_dict)

        # Return the AI-generated summary
        response_text = get_response_text(response_dict=response_dict)
        return response_text
