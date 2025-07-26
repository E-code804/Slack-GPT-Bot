import os

from services.openai_service import OpenAIService
from services.slack_service import SlackService
from services.cache_service import get_pr_cache, set_pr_cache
from utils.server_utils import get_response_text
import httpx


class PRService:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.openai_service = OpenAIService()
        self.slack_service = SlackService()

    # Background task to process PR and send result back to Slack
    async def process_pr_summary(self, pr_url: str, response_url: str):
        cached_summary = await get_pr_cache(pr_url=pr_url)

        if cached_summary:
            response_text = get_response_text(cached_summary)
            await self.slack_service.send_to_slack_response_url(
                response_url, response_text
            )
        else:
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
                    files_changed = pr_data.get(
                        "changed_files", 0
                    )  # Files changed count
                    additions = pr_data.get("additions", 0)
                    deletions = pr_data.get("deletions", 0)

                    # print(f"PR Title: {title}")
                    # print(f"PR Description: {description}")
                    # print(f"Files changed: {files_changed}")
                    # print(f"Additions: +{additions}, Deletions: -{deletions}")
                    # print(f"Diff content length: {len(diff_content)} characters")

                    # Use OpenAI to summarize the PR
                    summary = self.openai_service.summarize_pr(
                        title, description, diff_content
                    )

                    response_dict = {
                        "author": author,
                        "files_changes": files_changed,
                        "additions": additions,
                        "deletions": deletions,
                        "html_url": html_url,
                        "status": state,
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

            except Exception as e:
                error_msg = f"❌ Error analyzing PR: {str(e)}"
                await self.send_to_slack_response_url(response_url, error_msg)

    # # May want to move this to a slack service.
    # async def send_to_slack_response_url(self, response_url: str, response_text: str):
    #     # Send delated response back to slack
    #     try:
    #         async with httpx.AsyncClient(timeout=10.0) as client:
    #             payload = {
    #                 "text": response_text,
    #                 "response_type": "in_channel",  # or "ephemeral" for private
    #             }
    #             await client.post(response_url, json=payload)
    #     except Exception as e:
    #         print(f"Failed to send response to Slack: {e}")
