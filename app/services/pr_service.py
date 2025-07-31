import os
import httpx

from services.openai_service import OpenAIService
from services.slack_service import SlackService
from services.cache_service import (
    del_pr_cache,
    get_pr_cache,
    set_pr_cache,
    update_pr_state_cache,
)

from utils.server_utils import get_response_text

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


# TODO: Use webhooks to monitor when a PR is merged/updated/reject so cache is updated as well.
class PRService:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.openai_service = OpenAIService()
        self.slack_service = SlackService()
        self.client = WebClient(token=os.getenv("BOT_USER_OAUTH_TOKEN"))

    # Handle sending messages to a slack channel
    async def send_msg_to_slack_channel(self, slack_message: str, channel: str):
        try:
            # Send to slack
            result = self.client.chat_postMessage(
                channel=os.getenv("SLACK_GPT_BOT_CHANNEL_ID"),
                text=slack_message,
            )

            if result["ok"]:
                print(f"Slack message sent successfully: {result['ts']}")
                return {
                    "status": "success",
                    "message": "Slack message sent successfully",
                    "data": {"timestamp": result["ts"], "channel": result["channel"]},
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

    # Background task to process PR and send result back to Slack
    # TODO: Make the else block in a separate function.
    async def process_pr_summary(self, pr_url: str, response_url: str):
        try:
            cached_summary = await get_pr_cache(pr_url=pr_url)

            if cached_summary:
                response_text = get_response_text(cached_summary)
                await self.slack_service.send_to_slack_response_url(
                    response_url, response_text
                )

            else:
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
                    files_changed = pr_data.get(
                        "changed_files", 0
                    )  # Files changed count
                    additions = pr_data.get("additions", 0)
                    deletions = pr_data.get("deletions", 0)

                    # print_pr_info(title, description, files_changed, additions, deletions, diff_content)

                    # Use OpenAI to summarize the PR
                    summary = self.openai_service.summarize_pr(
                        title, description, diff_content
                    )

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

                    # Send the response text back to slack using the response url
                    await self.slack_service.send_to_slack_response_url(
                        response_url, response_text
                    )

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
